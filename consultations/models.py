"""Consultation and admission models."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from common.models import UUIDTimestampedModel


class Consultation(UUIDTimestampedModel):
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="consultations",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="consultations",
        limit_choices_to={"role": "doctor"},
    )
    diagnosis = models.TextField()
    treatment = models.TextField()
    prescription = models.TextField(blank=True)
    admitted = models.BooleanField(default=False, db_index=True)
    discharged = models.BooleanField(default=False, db_index=True)
    consultation_notes = models.TextField(blank=True)
    admitted_at = models.DateTimeField(null=True, blank=True)
    discharged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "admitted", "discharged"]),
            models.Index(fields=["doctor", "discharged"]),
        ]

    def __str__(self) -> str:
        return f"Consultation {self.patient.patient_number}"
