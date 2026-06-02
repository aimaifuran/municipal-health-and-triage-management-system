"""Custom user and clinic models."""

from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from common.models import UUIDTimestampedModel


class UserRole(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Admin"
    DOCTOR = "doctor", "Doctor"
    NURSE = "nurse", "Nurse"
    RECEPTIONIST = "receptionist", "Receptionist"
    API_CONSUMER = "api_consumer", "Public API Consumer"


class Clinic(UUIDTimestampedModel):
    name = models.CharField(max_length=255)
    address = models.TextField()
    municipality = models.CharField(max_length=255, db_index=True)
    region = models.CharField(max_length=255, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["region", "municipality"]),
        ]

    def __str__(self) -> str:
        return self.name


class UserManager(BaseUserManager):
    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> User:
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.SUPER_ADMIN)
        extra_fields.setdefault("is_verified", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=32, choices=UserRole.choices, db_index=True)
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff",
    )
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    profile_picture_url = models.URLField(max_length=500, blank=True)
    profile_picture_public_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]
        indexes = [
            models.Index(fields=["role", "clinic"]),
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def increment_failed_login(self) -> None:
        self.failed_login_attempts += 1
        self.save(update_fields=["failed_login_attempts"])

    def reset_failed_login(self) -> None:
        if self.failed_login_attempts:
            self.failed_login_attempts = 0
            self.save(update_fields=["failed_login_attempts"])


class DoctorPatientAssignment(UUIDTimestampedModel):
    """Tracks which patients a doctor is assigned to (anti-IDOR)."""

    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="patient_assignments",
        limit_choices_to={"role": UserRole.DOCTOR},
    )
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="doctor_assignments",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("doctor", "patient")]
        indexes = [
            models.Index(fields=["doctor", "is_active"]),
        ]
