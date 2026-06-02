"""Triage business logic and priority scoring."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction

from accounts.assignment import DoctorAssignmentService
from auditlogs.models import AuditAction
from auditlogs.services import AuditService
from triage.models import SeverityLevel, TriageRecord, TriageStatus
from triage.severity_engine import ClinicalTriageEngine, TriageAssessment
from triage.severity_engine import patient_age_years as compute_patient_age_years

if TYPE_CHECKING:
    from django.http import HttpRequest

    from accounts.models import User
    from patients.models import Patient


class PriorityCalculator:
    """Calculate patient priority and severity from clinical triage rules."""

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
        patient: Patient | None = None,
        patient_age_years: int | None = None,
        patient_sex: str | None = None,
    ) -> TriageAssessment:
        age = patient_age_years
        sex = patient_sex
        if patient is not None:
            age = age if age is not None else compute_patient_age_years(patient.birth_date)
            sex = sex if sex is not None else getattr(patient, "gender", None)
        return ClinicalTriageEngine.assess(
            oxygen_saturation=oxygen_saturation,
            body_temperature=body_temperature,
            heart_rate=heart_rate,
            respiratory_rate=respiratory_rate,
            blood_pressure=blood_pressure,
            symptoms=symptoms,
            patient_age_years=age,
            patient_sex=sex,
        )

    @classmethod
    def calculate(
        cls,
        *,
        oxygen_saturation: Decimal,
        body_temperature: Decimal,
        heart_rate: int,
        blood_pressure: str,
        symptoms: str,
        respiratory_rate: int | None = None,
        patient: Patient | None = None,
        patient_age_years: int | None = None,
        patient_sex: str | None = None,
    ) -> tuple[int, str]:
        """Backward-compatible API: returns (priority_score, severity_level)."""
        if respiratory_rate is None:
            respiratory_rate = 16
        assessment = cls.assess(
            oxygen_saturation=oxygen_saturation,
            body_temperature=body_temperature,
            heart_rate=heart_rate,
            respiratory_rate=respiratory_rate,
            blood_pressure=blood_pressure,
            symptoms=symptoms,
            patient=patient,
            patient_age_years=patient_age_years,
            patient_sex=patient_sex,
        )
        return assessment.priority_score, assessment.severity_level


class TriageService:
    @staticmethod
    @transaction.atomic
    def create_triage(
        *,
        patient,
        nurse: User,
        validated_data: dict,
        request: HttpRequest | None = None,
    ) -> TriageRecord:
        assessment = PriorityCalculator.assess(
            oxygen_saturation=validated_data["oxygen_saturation"],
            body_temperature=validated_data["body_temperature"],
            heart_rate=validated_data["heart_rate"],
            respiratory_rate=validated_data["respiratory_rate"],
            blood_pressure=validated_data["blood_pressure"],
            symptoms=validated_data["symptoms"],
            patient=patient,
        )
        score, severity = assessment.priority_score, assessment.severity_level
        TriageRecord.objects.filter(patient=patient, is_active=True).update(
            is_active=False,
            triage_status=TriageStatus.COMPLETED,
        )
        record = TriageRecord.objects.create(
            patient=patient,
            nurse=nurse,
            severity_level=severity,
            priority_score=score,
            triage_status=(
                TriageStatus.ESCALATED
                if severity == SeverityLevel.CRITICAL
                else TriageStatus.WAITING
            ),
            **validated_data,
        )
        AuditService.log(
            action=AuditAction.CREATE,
            object_type="TriageRecord",
            object_id=str(record.id),
            user=nurse,
            request=request,
            details=assessment.to_audit_details(),
        )
        DoctorAssignmentService.assign_patient_to_clinic_doctors(patient)
        return record

    @staticmethod
    @transaction.atomic
    def update_vitals(
        record: TriageRecord, validated_data: dict, user: User, request=None
    ) -> TriageRecord:
        for key, value in validated_data.items():
            setattr(record, key, value)
        assessment = PriorityCalculator.assess(
            oxygen_saturation=record.oxygen_saturation,
            body_temperature=record.body_temperature,
            heart_rate=record.heart_rate,
            respiratory_rate=record.respiratory_rate,
            blood_pressure=record.blood_pressure,
            symptoms=record.symptoms,
            patient=record.patient,
        )
        score, severity = assessment.priority_score, assessment.severity_level
        record.priority_score = score
        record.severity_level = severity
        if severity == SeverityLevel.CRITICAL:
            record.triage_status = TriageStatus.ESCALATED
        record.save()
        AuditService.log(
            action=AuditAction.UPDATE,
            object_type="TriageRecord",
            object_id=str(record.id),
            user=user,
            request=request,
            details=assessment.to_audit_details(),
        )
        DoctorAssignmentService.assign_patient_to_clinic_doctors(record.patient)
        return record
