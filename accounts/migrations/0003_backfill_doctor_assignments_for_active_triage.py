"""Backfill doctor assignments for patients already in the active triage queue."""
from django.db import migrations


def backfill_assignments(apps, schema_editor):
    Patient = apps.get_model("patients", "Patient")
    TriageRecord = apps.get_model("triage", "TriageRecord")
    User = apps.get_model("accounts", "User")
    DoctorPatientAssignment = apps.get_model("accounts", "DoctorPatientAssignment")

    patient_ids = (
        TriageRecord.objects.filter(is_active=True)
        .values_list("patient_id", flat=True)
        .distinct()
    )
    for patient in Patient.objects.filter(id__in=patient_ids).only("id", "clinic_id"):
        if not patient.clinic_id:
            continue
        doctors = User.objects.filter(
            role="doctor",
            clinic_id=patient.clinic_id,
            is_active=True,
        )
        for doctor in doctors:
            assignment, created = DoctorPatientAssignment.objects.get_or_create(
                doctor=doctor,
                patient=patient,
                defaults={"is_active": True},
            )
            if not created and not assignment.is_active:
                assignment.is_active = True
                assignment.save(update_fields=["is_active", "updated_at"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
        ("patients", "0001_initial"),
        ("triage", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_assignments, noop_reverse),
    ]
