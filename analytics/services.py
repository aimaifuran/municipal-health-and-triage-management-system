"""Analytics aggregation services — no PHI in public methods."""

from __future__ import annotations

from django.db.models import Count

from accounts.models import Clinic
from consultations.models import Consultation
from patients.models import Patient
from triage.models import SeverityLevel, TriageRecord


class AnalyticsService:
    @staticmethod
    def clinic_statistics(clinic_id) -> dict:
        if not clinic_id:
            return {}
        patients = Patient.objects.filter(clinic_id=clinic_id).count()
        active_triage = TriageRecord.objects.filter(
            patient__clinic_id=clinic_id,
            is_active=True,
        ).count()
        critical = TriageRecord.objects.filter(
            patient__clinic_id=clinic_id,
            is_active=True,
            severity_level=SeverityLevel.CRITICAL,
        ).count()
        admitted = Consultation.objects.filter(
            patient__clinic_id=clinic_id,
            admitted=True,
            discharged=False,
        ).count()
        severity_dist = (
            TriageRecord.objects.filter(patient__clinic_id=clinic_id, is_active=True)
            .values("severity_level")
            .annotate(count=Count("id"))
        )
        return {
            "clinic_id": str(clinic_id),
            "total_patients": patients,
            "active_triage": active_triage,
            "critical_cases": critical,
            "admitted_patients": admitted,
            "severity_distribution": list(severity_dist),
        }

    @staticmethod
    def regional_statistics(region: str = "") -> dict:
        clinics = Clinic.objects.filter(is_active=True)
        if region:
            clinics = clinics.filter(region__iexact=region)
        clinic_count = clinics.count()
        clinic_ids = list(clinics.values_list("id", flat=True))
        active_cases = TriageRecord.objects.filter(
            patient__clinic_id__in=clinic_ids,
            is_active=True,
        ).count()
        respiratory = (
            TriageRecord.objects.filter(
                patient__clinic_id__in=clinic_ids,
                is_active=True,
                symptoms__icontains="cough",
            ).count()
            + TriageRecord.objects.filter(
                patient__clinic_id__in=clinic_ids,
                is_active=True,
                symptoms__icontains="breath",
            ).count()
        )
        return {
            "region": region or "All Regions",
            "clinic_count": clinic_count,
            "active_cases": active_cases,
            "respiratory_cases": respiratory,
        }

    @staticmethod
    def _top_symptoms_for_region(clinic_ids: list) -> list[str]:
        if not clinic_ids:
            return ["Fever", "Cough", "Headache"]
        rows = (
            TriageRecord.objects.filter(
                patient__clinic_id__in=clinic_ids,
                is_active=True,
            )
            .exclude(symptoms="")
            .values_list("symptoms", flat=True)[:50]
        )
        counts: dict[str, int] = {}
        for text in rows:
            for token in text.replace(",", " ").split():
                word = token.strip().title()
                if len(word) > 2:
                    counts[word] = counts.get(word, 0) + 1
        if not counts:
            return ["Fever", "Cough", "Headache"]
        ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        return [name for name, _ in ranked[:5]]

    @staticmethod
    def _sample_critical_case(region: str) -> dict | None:
        clinics = Clinic.objects.filter(is_active=True)
        if region:
            clinics = clinics.filter(region__iexact=region)
        clinic_ids = list(clinics.values_list("id", flat=True))
        if not clinic_ids:
            return None
        triage = (
            TriageRecord.objects.filter(
                patient__clinic_id__in=clinic_ids,
                is_active=True,
                severity_level=SeverityLevel.CRITICAL,
            )
            .select_related("patient", "patient__clinic")
            .order_by("-priority_score", "-created_at")
            .first()
        )
        if not triage:
            triage = (
                TriageRecord.objects.filter(
                    patient__clinic_id__in=clinic_ids,
                    is_active=True,
                )
                .select_related("patient", "patient__clinic")
                .order_by("-priority_score", "-created_at")
                .first()
            )
        if not triage:
            return None
        patient = triage.patient
        consultation = Consultation.objects.filter(patient=patient).order_by("-created_at").first()
        if consultation and consultation.diagnosis:
            diagnosis = consultation.diagnosis
        else:
            diagnosis = "Under evaluation"
        age_note = ""
        if patient.birth_date:
            from triage.severity_engine import patient_age_years

            years = patient_age_years(patient.birth_date)
            if years is not None:
                age_note = f", {years}y"
        return {
            "patient_name": f"{patient.first_name} {patient.last_name}".strip(),
            "patient_details": (
                f"{patient.get_gender_display()}{age_note}, {patient.clinic.municipality}"
            ),
            "diagnosis": diagnosis,
            "contact_number": patient.contact_number,
            "address": patient.address,
            "severity_level": triage.severity_level,
            "symptoms": triage.symptoms,
        }

    @staticmethod
    def regional_health_report(region: str = "", *, masked: bool = True) -> dict:
        """
        Unified regional health report — same JSON shape for public and clinical consumers.

        When masked=True (public / API consumer): PHI fields are replaced.
        When masked=False (clinical JWT): includes real sample case from the database.
        """
        stats = AnalyticsService.regional_statistics(region)
        clinics = Clinic.objects.filter(is_active=True)
        if region:
            clinics = clinics.filter(region__iexact=region)
        clinic_ids = list(clinics.values_list("id", flat=True))
        report = {
            "region": stats.get("region", "All Regions"),
            "clinic_count": stats.get("clinic_count", 0),
            "active_cases": stats.get("active_cases", 0),
            "respiratory_cases": stats.get("respiratory_cases", 0),
            "top_symptoms": AnalyticsService._top_symptoms_for_region(clinic_ids),
            "data_classification": "public_masked" if masked else "clinical_full",
            "sample_cases": [],
        }
        if masked:
            report.update(
                {
                    "patient_name": "HIPAA Restricted",
                    "patient_details": "HIPAA Restricted",
                    "diagnosis": "HIPAA Restricted",
                    "contact_number": "HIPAA Restricted",
                    "address": "HIPAA Restricted",
                }
            )
            return report

        sample = AnalyticsService._sample_critical_case(region)
        if sample:
            report["sample_cases"] = [sample]
            report.update(
                {
                    "patient_name": sample["patient_name"],
                    "patient_details": sample["patient_details"],
                    "diagnosis": sample["diagnosis"],
                    "contact_number": sample["contact_number"],
                    "address": sample["address"],
                }
            )
        else:
            report.update(
                {
                    "patient_name": "No active cases",
                    "patient_details": "N/A",
                    "diagnosis": "N/A",
                    "contact_number": "N/A",
                    "address": "N/A",
                }
            )
        return report

    @staticmethod
    def public_masked_stats(region: str = "") -> dict:
        """HIPAA-safe public response — never expose PHI."""
        return AnalyticsService.regional_health_report(region, masked=True)
