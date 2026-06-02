"""
Clinical triage engine for severity and priority scoring.

Maps emergency-medicine triage tiers (RED/ORANGE/YELLOW/GREEN) to
SeverityLevel values (critical / moderate / stable). Used only for triage scoring.
See docs/TRIAGE_SEVERITY_EVALUATION.md for full documentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

from triage.models import SeverityLevel


class TriageTier(str, Enum):
    RED = "RED"
    ORANGE = "ORANGE"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


# Substring phrases — case-insensitive match in symptoms text
RED_FLAG_SYMPTOMS = frozenset(
    {
        "difficulty breathing",
        "respiratory distress",
        "shortness of breath",
        "cyanosis",
        "stopped breathing",
        "not breathing",
        "gasping",
        "choking",
        "severe bleeding",
        "hemorrhage",
        "uncontrolled bleeding",
        "shock",
        "no pulse",
        "unconscious",
        "unresponsive",
        "seizure",
        "stroke",
        "altered mental status",
        "altered consciousness",
        "one-sided weakness",
        "slurred speech",
        "sudden confusion",
        "chest pain",
        "cardiac arrest",
        "severe arrhythmia",
        "major trauma",
        "gunshot",
        "stab wound",
        "severe burns",
        "spinal injury",
        "head injury",
        "meningitis",
        "septic",
        "sepsis",
        "severe vaginal bleeding",
        "eclampsia",
        "overdose",
        "poisoning",
        "cold sweats",
    }
)

ORANGE_FLAG_SYMPTOMS = frozenset(
    {
        "severe pain",
        "persistent vomiting",
        "dehydration",
        "high fever",
        "palpitations",
        "dizziness",
        "weakness",
        "numbness",
        "facial drooping",
    }
)

CHRONIC_CONDITION_KEYWORDS = frozenset(
    {
        "diabetes",
        "diabetic",
        "hypertension",
        "hypertensive",
        "heart disease",
        "cardiac disease",
        "immunocompromised",
        "immunosuppressed",
        "cancer",
        "chemotherapy",
    }
)

PREGNANCY_KEYWORDS = frozenset(
    {
        "pregnant",
        "pregnancy",
        "prenatal",
        "obstetric",
        "trimester",
        "eclampsia",
        "preeclampsia",
    }
)


@dataclass(frozen=True)
class TriageAssessment:
    """Full triage analysis (severity domain only)."""

    severity_level: str
    priority_score: int
    triage_tier: TriageTier
    requires_immediate_attention: bool
    possible_conditions: list[str] = field(default_factory=list)
    critical_findings: list[str] = field(default_factory=list)
    recommended_action: str = ""
    triage_reasoning: str = ""

    def to_audit_details(self) -> dict:
        return {
            "triage_tier": self.triage_tier.value,
            "priority_score": self.priority_score,
            "severity_level": self.severity_level,
            "requires_immediate_attention": self.requires_immediate_attention,
            "possible_conditions": self.possible_conditions,
            "critical_findings": self.critical_findings,
            "recommended_action": self.recommended_action,
            "triage_reasoning": self.triage_reasoning,
        }


def patient_age_years(birth_date: date | None, *, on_date: date | None = None) -> int | None:
    if not birth_date:
        return None
    today = on_date or date.today()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return max(years, 0)


def _parse_systolic(blood_pressure: str) -> int | None:
    try:
        return int(blood_pressure.split("/")[0].strip())
    except (ValueError, IndexError, AttributeError):
        return None


def _symptoms_contain(symptoms_lower: str, phrases: frozenset[str]) -> list[str]:
    return [p for p in phrases if p in symptoms_lower]


def _tier_to_severity(tier: TriageTier) -> str:
    if tier == TriageTier.RED:
        return SeverityLevel.CRITICAL
    if tier in (TriageTier.ORANGE, TriageTier.YELLOW):
        return SeverityLevel.MODERATE
    return SeverityLevel.STABLE


def _tier_base_score(tier: TriageTier) -> int:
    return {
        TriageTier.RED: 88,
        TriageTier.ORANGE: 68,
        TriageTier.YELLOW: 42,
        TriageTier.GREEN: 12,
    }[tier]


def _recommended_action(tier: TriageTier) -> str:
    return {
        TriageTier.RED: (
            "Immediate emergency intervention — activate critical care pathway and "
            "continuous monitoring now."
        ),
        TriageTier.ORANGE: (
            "Urgent physician evaluation within minutes — prepare resuscitation "
            "equipment if condition worsens."
        ),
        TriageTier.YELLOW: (
            "Medical assessment required — monitor vitals and re-triage if symptoms worsen."
        ),
        TriageTier.GREEN: (
            "Routine clinic assessment when capacity allows — educate on return precautions."
        ),
    }[tier]


class ClinicalTriageEngine:
    """Emergency-physician-style triage for municipal health settings."""

    @classmethod
    def assess(
        cls,
        *,
        oxygen_saturation: Decimal,
        body_temperature: Decimal,
        heart_rate: int,
        respiratory_rate: int,
        blood_pressure: str,
        symptoms: str,
        patient_age_years: int | None = None,
        patient_sex: str | None = None,
    ) -> TriageAssessment:
        symptoms_lower = (symptoms or "").lower()
        systolic = _parse_systolic(blood_pressure)
        findings: list[str] = []
        conditions: list[str] = []
        risk_points = 0
        forced_red = False

        red_symptoms = _symptoms_contain(symptoms_lower, RED_FLAG_SYMPTOMS)
        if red_symptoms:
            forced_red = True
            findings.extend(s.title() for s in red_symptoms[:4])

        # --- Vital sign interpretation (clinical rules) ---
        spo2 = float(oxygen_saturation)
        temp = float(body_temperature)
        hr = heart_rate
        rr = respiratory_rate

        if spo2 < 90:
            forced_red = True
            findings.append(f"SpO₂ {spo2}% (critical hypoxia)")
            conditions.append("Respiratory distress / hypoxemia")
        elif spo2 <= 93:
            risk_points += 25
            findings.append(f"SpO₂ {spo2}% (high risk)")
            conditions.append("Possible respiratory compromise")

        if hr > 130 or hr < 40:
            forced_red = True
            findings.append(f"Heart rate {hr} bpm (critical)")
            conditions.append("Hemodynamic instability")
        elif hr > 120 or hr < 50:
            risk_points += 18
            findings.append(f"Heart rate {hr} bpm (high risk)")

        if temp < 35.0:
            forced_red = True
            findings.append(f"Temperature {temp}°C (hypothermia)")
            conditions.append("Hypothermia / severe systemic illness")
        elif temp >= 39.5:
            risk_points += 18
            findings.append(f"Temperature {temp}°C (high fever)")
            conditions.append("Severe infection / sepsis risk")
        elif temp >= 38.0:
            risk_points += 8

        if rr > 30 or rr < 8:
            forced_red = True
            findings.append(f"Respiratory rate {rr}/min (critical)")
            conditions.append("Airway / breathing compromise")
        elif rr > 24 or rr < 10:
            risk_points += 12

        if systolic is not None:
            if systolic < 90:
                forced_red = True
                findings.append(f"Systolic BP {systolic} mmHg (critical)")
                conditions.append("Shock / hypotension")
            elif systolic > 200:
                forced_red = True
                findings.append(f"Systolic BP {systolic} mmHg (critical hypertension)")
                conditions.append("Hypertensive emergency risk")
            elif systolic > 180:
                risk_points += 20
                findings.append(f"Systolic BP {systolic} mmHg (high risk)")
                if "chest pain" in symptoms_lower:
                    forced_red = True
                    conditions.append("Possible acute coronary syndrome")
            elif systolic >= 160:
                risk_points += 10

        # High fever with confusion → RED
        if temp >= 38.5 and any(
            p in symptoms_lower for p in ("confusion", "altered", "unresponsive", "lethargy")
        ):
            forced_red = True
            findings.append("High fever with altered mental status")
            conditions.append("Possible sepsis or CNS infection")

        # --- Special populations (increase consideration) ---
        population_note = []
        if patient_age_years is not None:
            if patient_age_years >= 65:
                risk_points += 8
                population_note.append("elderly")
            elif patient_age_years < 1:
                risk_points += 12
                population_note.append("infant")
            elif patient_age_years < 5:
                risk_points += 6
                population_note.append("pediatric")

        if _symptoms_contain(symptoms_lower, PREGNANCY_KEYWORDS):
            risk_points += 10
            population_note.append("pregnancy")
            if any(p in symptoms_lower for p in ("bleeding", "seizure", "eclampsia")):
                forced_red = True
                conditions.append("Obstetric emergency risk")

        if _symptoms_contain(symptoms_lower, CHRONIC_CONDITION_KEYWORDS):
            risk_points += 6
            population_note.append("chronic comorbidity")

        orange_symptoms = _symptoms_contain(symptoms_lower, ORANGE_FLAG_SYMPTOMS)
        risk_points += min(len(orange_symptoms) * 8, 24)

        # Multiple moderate abnormalities → treat as higher risk
        moderate_vital_count = sum(
            1
            for flag in (
                90 <= spo2 <= 93,
                100 < hr <= 120 or 50 <= hr < 60,
                38.0 <= temp < 39.5,
                systolic is not None and 160 <= systolic <= 180,
                20 <= rr <= 24 or 10 <= rr < 12,
            )
            if flag
        )
        if moderate_vital_count >= 2:
            risk_points += 15
            findings.append("Multiple abnormal vital signs")

        # --- Determine tier (when uncertain, choose higher) ---
        if forced_red:
            tier = TriageTier.RED
        elif risk_points >= 45 or red_symptoms or orange_symptoms:
            tier = TriageTier.ORANGE
        elif risk_points >= 22 or moderate_vital_count >= 1:
            tier = TriageTier.YELLOW
        else:
            tier = TriageTier.GREEN

        # Symptom-driven upgrade: stroke/cardiac/breathing never below ORANGE
        if red_symptoms and tier == TriageTier.GREEN:
            tier = TriageTier.ORANGE
        if forced_red:
            tier = TriageTier.RED

        score = min(100, _tier_base_score(tier) + min(risk_points // 3, 12))
        if tier == TriageTier.RED:
            score = max(score, 80)

        severity = _tier_to_severity(tier)
        requires_immediate = tier in (TriageTier.RED, TriageTier.ORANGE)

        if not conditions and tier == TriageTier.RED:
            conditions.append("Acute emergency — further evaluation required")
        if not conditions and tier == TriageTier.ORANGE:
            conditions.append("Potentially life-threatening presentation")

        reasoning_parts = [
            (
                f"Triage tier {tier.value} based on vitals, symptoms, "
                "and emergency medicine principles."
            ),
        ]
        if findings:
            reasoning_parts.append("Key findings: " + "; ".join(findings[:5]) + ".")
        if population_note:
            reasoning_parts.append(
                "Special population factors: " + ", ".join(population_note) + "."
            )
        if tier in (TriageTier.RED, TriageTier.ORANGE):
            reasoning_parts.append("When uncertain, higher acuity was selected for patient safety.")

        return TriageAssessment(
            severity_level=severity,
            priority_score=score,
            triage_tier=tier,
            requires_immediate_attention=requires_immediate,
            possible_conditions=list(dict.fromkeys(conditions))[:6],
            critical_findings=findings[:8],
            recommended_action=_recommended_action(tier),
            triage_reasoning=" ".join(reasoning_parts),
        )
