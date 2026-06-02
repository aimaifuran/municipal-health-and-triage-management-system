"""Triage records and priority scoring."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from common.models import UUIDTimestampedModel
from common.validators import (
    validate_blood_pressure,
    validate_body_temperature,
    validate_heart_rate,
    validate_oxygen_saturation,
    validate_respiratory_rate,
)


class SeverityLevel(models.TextChoices):
    CRITICAL = "critical", "Critical"
    MODERATE = "moderate", "Moderate"
    STABLE = "stable", "Stable"


class TriageStatus(models.TextChoices):
    WAITING = "waiting", "Waiting"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    ESCALATED = "escalated", "Escalated"


class TriageRecord(UUIDTimestampedModel):
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="triage_records",
    )
    nurse = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="triage_records",
    )
    blood_pressure = models.CharField(max_length=16, validators=[validate_blood_pressure])
    heart_rate = models.PositiveSmallIntegerField(validators=[validate_heart_rate])
    respiratory_rate = models.PositiveSmallIntegerField(validators=[validate_respiratory_rate])
    oxygen_saturation = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[validate_oxygen_saturation],
    )
    body_temperature = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        validators=[validate_body_temperature],
    )
    symptoms = models.TextField()
    severity_level = models.CharField(
        max_length=16,
        choices=SeverityLevel.choices,
        db_index=True,
    )
    priority_score = models.PositiveSmallIntegerField(default=0, db_index=True)
    triage_status = models.CharField(
        max_length=16,
        choices=TriageStatus.choices,
        default=TriageStatus.WAITING,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-priority_score", "-created_at"]
        indexes = [
            models.Index(fields=["patient", "is_active"]),
            models.Index(fields=["severity_level", "triage_status"]),
        ]

    def __str__(self) -> str:
        return f"Triage {self.patient.patient_number} - {self.severity_level}"
