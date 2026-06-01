"""Consultation, admit, discharge, and bulk discharge services."""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from auditlogs.models import AuditAction
from auditlogs.services import AuditService
from consultations.models import Consultation
from security.access import AccessControlService
from triage.models import TriageRecord, TriageStatus

if TYPE_CHECKING:
    from accounts.models import User
    from django.http import HttpRequest
    from patients.models import Patient


class ConsultationService:
    @staticmethod
    def get_open_consultation(patient: Patient, doctor: User) -> Consultation | None:
        return (
            Consultation.objects.filter(
                patient=patient,
                doctor=doctor,
                discharged=False,
            )
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    @transaction.atomic
    def upsert_consultation(
        *,
        patient: Patient,
        doctor: User,
        validated_data: dict,
        request: HttpRequest | None = None,
    ) -> Consultation:
        consultation = ConsultationService.get_open_consultation(patient, doctor)
        if consultation:
            for field, value in validated_data.items():
                setattr(consultation, field, value)
            consultation.save()
            AuditService.log(
                action=AuditAction.UPDATE,
                object_type="Consultation",
                object_id=str(consultation.id),
                user=doctor,
                request=request,
                details={"action": "update_consultation"},
            )
            return consultation
        return ConsultationService.create_consultation(
            patient=patient,
            doctor=doctor,
            validated_data=validated_data,
            request=request,
        )

    @staticmethod
    @transaction.atomic
    def save_and_admit(
        *,
        patient: Patient,
        doctor: User,
        validated_data: dict,
        request: HttpRequest | None = None,
    ) -> Consultation:
        consultation = ConsultationService.upsert_consultation(
            patient=patient,
            doctor=doctor,
            validated_data=validated_data,
            request=request,
        )
        if not consultation.admitted:
            ConsultationService.admit_patient(consultation, doctor, request)
        return consultation

    @staticmethod
    def _close_active_triage(patient: Patient) -> None:
        TriageRecord.objects.filter(patient=patient, is_active=True).update(
            is_active=False,
            triage_status=TriageStatus.COMPLETED,
        )

    @staticmethod
    def _reopen_triage(patient: Patient) -> None:
        record = TriageRecord.objects.filter(patient=patient).order_by("-created_at").first()
        if not record:
            return
        record.is_active = True
        record.triage_status = TriageStatus.WAITING
        record.save(update_fields=["is_active", "triage_status", "updated_at"])

    @staticmethod
    @transaction.atomic
    def create_consultation(
        *,
        patient: Patient,
        doctor: User,
        validated_data: dict,
        request: HttpRequest | None = None,
    ) -> Consultation:
        consultation = Consultation.objects.create(
            patient=patient,
            doctor=doctor,
            **validated_data,
        )
        AuditService.log(
            action=AuditAction.CREATE,
            object_type="Consultation",
            object_id=str(consultation.id),
            user=doctor,
            request=request,
        )
        return consultation

    @staticmethod
    @transaction.atomic
    def admit_patient(consultation: Consultation, user: User, request=None) -> Consultation:
        consultation.admitted = True
        consultation.admitted_at = timezone.now()
        consultation.save(update_fields=["admitted", "admitted_at", "updated_at"])
        AuditService.log(
            action=AuditAction.ADMIT,
            object_type="Consultation",
            object_id=str(consultation.id),
            user=user,
            request=request,
        )
        return consultation

    @staticmethod
    @transaction.atomic
    def discharge_patient(consultation: Consultation, user: User, request=None) -> Consultation:
        consultation.discharged = True
        consultation.discharged_at = timezone.now()
        consultation.save(update_fields=["discharged", "discharged_at", "updated_at"])
        ConsultationService._close_active_triage(consultation.patient)
        AuditService.log(
            action=AuditAction.DISCHARGE,
            object_type="Consultation",
            object_id=str(consultation.id),
            user=user,
            request=request,
        )
        return consultation

    @staticmethod
    @transaction.atomic
    def bulk_discharge(
        consultation_ids: list,
        user: User,
        request: HttpRequest | None = None,
    ) -> dict:
        results = {"success": [], "failed": []}
        normalized_ids = [str(cid).strip() for cid in consultation_ids if cid and str(cid).strip()]
        if not normalized_ids:
            return results

        eligible = AccessControlService.filter_consultations_for_user(
            user,
            Consultation.objects.filter(
                id__in=normalized_ids,
                admitted=True,
                discharged=False,
            ),
        )
        found_ids: set[str] = set()
        for consultation in eligible:
            found_ids.add(str(consultation.id))
            consultation.discharged = True
            consultation.discharged_at = timezone.now()
            consultation.save(update_fields=["discharged", "discharged_at", "updated_at"])
            ConsultationService._close_active_triage(consultation.patient)
            results["success"].append(str(consultation.id))

        for cid in normalized_ids:
            if cid in found_ids or cid in results["success"]:
                continue
            results["failed"].append({
                "id": cid,
                "reason": ConsultationService._bulk_discharge_failure_reason(cid, user),
            })

        if results["success"] or results["failed"]:
            AuditService.log(
                action=AuditAction.BULK_DISCHARGE,
                object_type="Consultation",
                object_id=",".join(results["success"][:10]),
                user=user,
                request=request,
                details={
                    "success_count": len(results["success"]),
                    "failed_count": len(results["failed"]),
                },
            )
        return results

    @staticmethod
    def _bulk_discharge_failure_reason(consultation_id: str, user: User) -> str:
        from accounts.models import UserRole

        try:
            consultation = Consultation.objects.select_related("patient", "doctor").get(
                id=consultation_id
            )
        except Consultation.DoesNotExist:
            return "Record not found — refresh the page and try again."

        if user.role != UserRole.SUPER_ADMIN and consultation.doctor_id != user.id:
            return "Assigned to another doctor."
        if consultation.discharged:
            return "Already discharged — refresh the list."
        if not consultation.admitted:
            return "Patient is not admitted."
        return "Not eligible for discharge."

    @staticmethod
    @transaction.atomic
    def bulk_readmit(
        consultation_ids: list,
        user: User,
        request: HttpRequest | None = None,
    ) -> dict:
        """Undo discharge — return patients to the active discharge list."""
        results = {"success": [], "failed": []}
        normalized_ids = [str(cid).strip() for cid in consultation_ids if cid and str(cid).strip()]
        if not normalized_ids:
            return results

        eligible = AccessControlService.filter_consultations_for_user(
            user,
            Consultation.objects.filter(
                id__in=normalized_ids,
                admitted=True,
                discharged=True,
            ),
        )
        found_ids: set[str] = set()
        for consultation in eligible:
            found_ids.add(str(consultation.id))
            consultation.discharged = False
            consultation.discharged_at = None
            consultation.save(update_fields=["discharged", "discharged_at", "updated_at"])
            ConsultationService._reopen_triage(consultation.patient)
            results["success"].append(str(consultation.id))

        for cid in normalized_ids:
            if cid in found_ids or cid in results["success"]:
                continue
            results["failed"].append({
                "id": cid,
                "reason": ConsultationService._bulk_readmit_failure_reason(cid, user),
            })

        if results["success"] or results["failed"]:
            AuditService.log(
                action=AuditAction.UPDATE,
                object_type="Consultation",
                object_id=",".join(results["success"][:10]),
                user=user,
                request=request,
                details={
                    "action": "bulk_readmit",
                    "success_count": len(results["success"]),
                    "failed_count": len(results["failed"]),
                },
            )
        return results

    @staticmethod
    def _bulk_readmit_failure_reason(consultation_id: str, user: User) -> str:
        from accounts.models import UserRole

        try:
            consultation = Consultation.objects.select_related("patient", "doctor").get(
                id=consultation_id
            )
        except Consultation.DoesNotExist:
            return "Record not found — refresh the page and try again."

        if user.role != UserRole.SUPER_ADMIN and consultation.doctor_id != user.id:
            return "Assigned to another doctor."
        if not consultation.discharged:
            return "Patient is not discharged."
        if not consultation.admitted:
            return "Patient was not admitted."
        return "Not eligible to restore."
