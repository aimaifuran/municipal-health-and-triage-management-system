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
    def public_masked_stats(region: str = "") -> dict:
        """HIPAA-safe public response — never expose PHI."""
        stats = AnalyticsService.regional_statistics(region)
        top_symptoms = ["Fever", "Cough", "Headache"]
        return {
            "region": stats.get("region", "Region VII"),
            "clinic_count": stats.get("clinic_count", 0),
            "active_cases": stats.get("active_cases", 0),
            "respiratory_cases": stats.get("respiratory_cases", 0),
            "top_symptoms": top_symptoms,
            "patient_name": "HIPAA Restricted",
            "patient_details": "HIPAA Restricted",
            "diagnosis": "HIPAA Restricted",
            "contact_number": "HIPAA Restricted",
            "address": "HIPAA Restricted",
        }
