"""Anti-IDOR queryset filtering and access validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import QuerySet

from accounts.models import DoctorPatientAssignment, UserRole
from auditlogs.models import AuditAction
from auditlogs.services import AuditService
from common.exceptions import AntiIDORViolation

if TYPE_CHECKING:
    from django.http import HttpRequest

    from accounts.models import User
    from patients.models import Patient


class AccessControlService:
    @staticmethod
    def filter_patients_for_user(user: User, queryset: QuerySet) -> QuerySet:
        if not getattr(user, "is_authenticated", False):
            return queryset.none()
        if user.role == UserRole.SUPER_ADMIN or user.is_superuser:
            return queryset
        if not user.clinic_id:
            return queryset.none()
        queryset = queryset.filter(clinic_id=user.clinic_id)
        if user.role == UserRole.DOCTOR:
            assigned_ids = DoctorPatientAssignment.objects.filter(
                doctor=user,
                is_active=True,
            ).values_list("patient_id", flat=True)
            return queryset.filter(id__in=assigned_ids)
        if user.role == UserRole.RECEPTIONIST:
            return queryset
        if user.role == UserRole.NURSE:
            return queryset
        return queryset.none()

    @staticmethod
    def can_access_patient(
        user: User, patient: Patient, request: HttpRequest | None = None
    ) -> bool:
        if not getattr(user, "is_authenticated", False):
            return False
        if user.role == UserRole.SUPER_ADMIN or user.is_superuser:
            return True
        if str(patient.clinic_id) != str(user.clinic_id):
            AuditService.log(
                action=AuditAction.UNAUTHORIZED_ACCESS,
                object_type="Patient",
                object_id=str(patient.id),
                user=user,
                request=request,
                details={"reason": "clinic_mismatch"},
            )
            return False
        if user.role == UserRole.DOCTOR:
            assigned = DoctorPatientAssignment.objects.filter(
                doctor=user,
                patient=patient,
                is_active=True,
            ).exists()
            if not assigned:
                AuditService.log(
                    action=AuditAction.UNAUTHORIZED_ACCESS,
                    object_type="Patient",
                    object_id=str(patient.id),
                    user=user,
                    request=request,
                    details={"reason": "not_assigned"},
                )
            return assigned
        if user.role in (UserRole.NURSE, UserRole.RECEPTIONIST):
            return True
        return False

    @staticmethod
    def assert_patient_access(user: User, patient: Patient, request=None) -> None:
        if not AccessControlService.can_access_patient(user, patient, request):
            raise AntiIDORViolation()

    @staticmethod
    def filter_consultations_for_user(user: User, queryset: QuerySet) -> QuerySet:
        if not getattr(user, "is_authenticated", False):
            return queryset.none()
        if user.role == UserRole.RECEPTIONIST:
            return queryset.none()
        if user.role == UserRole.SUPER_ADMIN or user.is_superuser:
            return queryset
        if user.role == UserRole.DOCTOR:
            return queryset.filter(doctor=user)
        if user.role == UserRole.NURSE:
            if user.clinic_id:
                return queryset.filter(patient__clinic_id=user.clinic_id)
            return queryset.none()
        return queryset.none()
