"""Patient registration and archive services."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from auditlogs.models import AuditAction
from auditlogs.services import AuditService
from patients.models import Patient

if TYPE_CHECKING:
    from django.http import HttpRequest

    from accounts.models import User


class PatientService:
    @staticmethod
    def generate_patient_number(clinic_id: str) -> str:
        suffix = secrets.token_hex(3).upper()
        return f"PAT-{str(clinic_id)[:8].upper()}-{suffix}"

    @staticmethod
    @transaction.atomic
    def create_patient(
        *,
        user: User,
        validated_data: dict,
        request: HttpRequest | None = None,
    ) -> Patient:
        clinic = validated_data.get("clinic") or user.clinic
        if not clinic:
            raise ValueError("Clinic is required")
        duplicate = Patient.objects.filter(
            first_name__iexact=validated_data["first_name"],
            last_name__iexact=validated_data["last_name"],
            birth_date=validated_data["birth_date"],
            clinic=clinic,
        ).exists()
        if duplicate:
            raise ValueError(
                "A patient with the same name and birth date already exists at this clinic."
            )
        patient = Patient.objects.create(
            patient_number=PatientService.generate_patient_number(str(clinic.id)),
            clinic=clinic,
            created_by=user,
            **validated_data,
        )
        AuditService.log(
            action=AuditAction.CREATE,
            object_type="Patient",
            object_id=str(patient.id),
            user=user,
            request=request,
        )
        return patient

    @staticmethod
    @transaction.atomic
    def archive_patient(patient: Patient, user: User, request=None) -> Patient:
        patient.archive()
        AuditService.log(
            action=AuditAction.ARCHIVE,
            object_type="Patient",
            object_id=str(patient.id),
            user=user,
            request=request,
        )
        return patient
