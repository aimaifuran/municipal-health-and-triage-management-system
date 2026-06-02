from decimal import Decimal

import pytest

from triage.models import SeverityLevel
from triage.services import PriorityCalculator
from triage.severity_engine import TriageTier


@pytest.mark.django_db
class TestPriorityCalculator:
    def test_critical_red_flags(self):
        assessment = PriorityCalculator.assess(
            oxygen_saturation=Decimal("84"),
            body_temperature=Decimal("38.9"),
            heart_rate=132,
            respiratory_rate=32,
            blood_pressure="88/60",
            symptoms="Chest pain, difficulty breathing, cold sweats",
            patient_age_years=67,
        )
        assert assessment.triage_tier == TriageTier.RED
        assert assessment.severity_level == SeverityLevel.CRITICAL
        assert assessment.priority_score >= 80
        assert assessment.requires_immediate_attention is True
        assert (
            "Chest pain" in " ".join(assessment.critical_findings).lower()
            or assessment.critical_findings
        )

    def test_calculate_backward_compatible(self):
        score, severity = PriorityCalculator.calculate(
            oxygen_saturation=Decimal("85"),
            body_temperature=Decimal("40.0"),
            heart_rate=130,
            blood_pressure="190/110",
            symptoms="chest pain and difficulty breathing",
            respiratory_rate=28,
        )
        assert score >= 80
        assert severity == SeverityLevel.CRITICAL

    def test_stable_green(self):
        assessment = PriorityCalculator.assess(
            oxygen_saturation=Decimal("98"),
            body_temperature=Decimal("36.8"),
            heart_rate=72,
            respiratory_rate=16,
            blood_pressure="120/80",
            symptoms="mild headache",
        )
        assert assessment.triage_tier == TriageTier.GREEN
        assert assessment.severity_level == SeverityLevel.STABLE

    def test_orange_high_risk_spo2(self):
        assessment = PriorityCalculator.assess(
            oxygen_saturation=Decimal("92"),
            body_temperature=Decimal("37.2"),
            heart_rate=88,
            respiratory_rate=18,
            blood_pressure="130/85",
            symptoms="persistent cough",
        )
        assert assessment.triage_tier in (TriageTier.ORANGE, TriageTier.YELLOW, TriageTier.RED)
        assert assessment.priority_score >= 30

    def test_elderly_increases_acuity(self, patient):
        from datetime import date, timedelta

        patient.birth_date = date.today() - timedelta(days=365 * 70)
        patient.save(update_fields=["birth_date"])
        assessment = PriorityCalculator.assess(
            oxygen_saturation=Decimal("96"),
            body_temperature=Decimal("38.2"),
            heart_rate=95,
            respiratory_rate=18,
            blood_pressure="140/90",
            symptoms="weakness and dizziness",
            patient=patient,
        )
        assert assessment.priority_score >= 30

    def test_assessment_json_fields(self):
        assessment = PriorityCalculator.assess(
            oxygen_saturation=Decimal("88"),
            body_temperature=Decimal("39.6"),
            heart_rate=125,
            respiratory_rate=26,
            blood_pressure="170/100",
            symptoms="severe pain and palpitations",
        )
        details = assessment.to_audit_details()
        assert details["triage_tier"] in ("RED", "ORANGE", "YELLOW", "GREEN")
        assert "triage_reasoning" in details
        assert "recommended_action" in details

    @pytest.mark.parametrize(
        "name,age,spo2,temp,hr,rr,bp,symptoms,allowed_tiers,allowed_severity,min_score,max_score",
        [
            (
                "critical_hypoxia_shock",
                67,
                "84",
                "38.9",
                132,
                32,
                "88/60",
                "Chest pain, difficulty breathing, cold sweats",
                (TriageTier.RED,),
                (SeverityLevel.CRITICAL,),
                80,
                100,
            ),
            (
                "stroke_pattern",
                58,
                "95",
                "37.1",
                96,
                18,
                "178/98",
                "Slurred speech and one-sided weakness",
                (TriageTier.RED,),
                (SeverityLevel.CRITICAL,),
                80,
                100,
            ),
            (
                "high_risk_respiratory",
                43,
                "91",
                "37.6",
                124,
                26,
                "152/94",
                "Persistent cough and weakness",
                (TriageTier.ORANGE, TriageTier.RED),
                (SeverityLevel.MODERATE, SeverityLevel.CRITICAL),
                55,
                100,
            ),
            (
                "moderate_multi_abnormal",
                35,
                "92",
                "38.4",
                104,
                22,
                "166/100",
                "Severe pain and dizziness",
                (TriageTier.ORANGE, TriageTier.YELLOW, TriageTier.RED),
                (SeverityLevel.MODERATE, SeverityLevel.CRITICAL),
                30,
                100,
            ),
            (
                "stable_followup",
                30,
                "99",
                "36.8",
                74,
                16,
                "118/78",
                "Mild headache",
                (TriageTier.GREEN,),
                (SeverityLevel.STABLE,),
                0,
                29,
            ),
        ],
    )
    def test_clinical_dataset_cases(
        self,
        name,
        age,
        spo2,
        temp,
        hr,
        rr,
        bp,
        symptoms,
        allowed_tiers,
        allowed_severity,
        min_score,
        max_score,
    ):
        assessment = PriorityCalculator.assess(
            oxygen_saturation=Decimal(spo2),
            body_temperature=Decimal(temp),
            heart_rate=hr,
            respiratory_rate=rr,
            blood_pressure=bp,
            symptoms=symptoms,
            patient_age_years=age,
        )
        assert assessment.triage_tier in allowed_tiers, name
        assert assessment.severity_level in allowed_severity, name
        assert min_score <= assessment.priority_score <= max_score, name
