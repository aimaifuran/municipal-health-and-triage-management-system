"""Patient demographic and document models."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from common.models import SoftDeleteModel
from common.validators import phone_validator


class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"
    PREFER_NOT = "prefer_not", "Prefer not to say"


class Patient(SoftDeleteModel):
    patient_number = models.CharField(max_length=32, unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    middle_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150)
    birth_date = models.DateField()
    gender = models.CharField(max_length=16, choices=Gender.choices)
    address = models.TextField()
    contact_number = models.CharField(max_length=20, validators=[phone_validator])
    emergency_contact = models.CharField(max_length=255)
    clinic = models.ForeignKey(
        "accounts.Clinic",
        on_delete=models.PROTECT,
        related_name="patients",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_patients",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "last_name", "first_name"]),
            models.Index(fields=["patient_number"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["first_name", "last_name", "birth_date", "clinic"],
                name="unique_patient_per_clinic",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.patient_number} - {self.full_name}"

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p).strip()


class PatientDocument(SoftDeleteModel):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    title = models.CharField(max_length=255)
    file_url = models.URLField(max_length=500)
    cloudinary_public_id = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    file_size_bytes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
