"""Doctor–patient assignment for clinic-scoped access control."""

from __future__ import annotations

from typing import TYPE_CHECKING

from accounts.models import DoctorPatientAssignment, User, UserRole

if TYPE_CHECKING:
    from patients.models import Patient


class DoctorAssignmentService:
    @staticmethod
    def assign_patient_to_clinic_doctors(patient: Patient) -> int:
        """
        Ensure all active doctors at the patient's clinic can access this patient.
        Idempotent: creates missing assignments and reactivates inactive ones.
        """
        if not patient.clinic_id:
            return 0

        doctors = User.objects.filter(
            role=UserRole.DOCTOR,
            clinic_id=patient.clinic_id,
            is_active=True,
        )
        count = 0
        for doctor in doctors:
            assignment, created = DoctorPatientAssignment.objects.get_or_create(
                doctor=doctor,
                patient=patient,
                defaults={"is_active": True},
            )
            if created:
                count += 1
            elif not assignment.is_active:
                assignment.is_active = True
                assignment.save(update_fields=["is_active", "updated_at"])
                count += 1
        return count
