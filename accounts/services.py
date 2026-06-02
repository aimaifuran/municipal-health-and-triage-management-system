"""Account and clinic administration for super admins."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest

from accounts.models import Clinic, UserRole
from auditlogs.models import AuditAction
from auditlogs.services import AuditService

User = get_user_model()

STAFF_ROLES = (
    UserRole.DOCTOR,
    UserRole.NURSE,
    UserRole.RECEPTIONIST,
)


class AdminAccountService:
    @staticmethod
    def create_clinic(
        *,
        actor: User,
        validated_data: dict[str, Any],
        request: HttpRequest | None = None,
    ) -> Clinic:
        with transaction.atomic():
            clinic = Clinic.objects.create(**validated_data)
            AuditService.log(
                action=AuditAction.CREATE,
                object_type="Clinic",
                object_id=str(clinic.pk),
                user=actor,
                request=request,
                details={"name": clinic.name},
            )
        return clinic

    @staticmethod
    def update_clinic(
        *,
        clinic: Clinic,
        actor: User,
        validated_data: dict[str, Any],
        request: HttpRequest | None = None,
    ) -> Clinic:
        with transaction.atomic():
            for field, value in validated_data.items():
                setattr(clinic, field, value)
            clinic.save()
            AuditService.log(
                action=AuditAction.UPDATE,
                object_type="Clinic",
                object_id=str(clinic.pk),
                user=actor,
                request=request,
                details={"name": clinic.name},
            )
        return clinic

    @staticmethod
    def create_staff_user(
        *,
        actor: User,
        validated_data: dict[str, Any],
        request: HttpRequest | None = None,
    ) -> User:
        password = validated_data.pop("password")
        role = validated_data.pop("role")
        if role not in STAFF_ROLES:
            raise ValueError("Invalid staff role.")
        clinic = validated_data.get("clinic")
        if not clinic:
            raise ValueError("Clinic is required for staff accounts.")

        with transaction.atomic():
            user = User.objects.create_user(
                email=validated_data["email"],
                password=password,
                first_name=validated_data.get("first_name", ""),
                last_name=validated_data.get("last_name", ""),
                role=role,
                clinic=clinic,
                is_active=validated_data.get("is_active", True),
                is_verified=validated_data.get("is_verified", True),
            )
            AuditService.log(
                action=AuditAction.CREATE,
                object_type="User",
                object_id=str(user.pk),
                user=actor,
                request=request,
                details={"email": user.email, "role": role},
            )
        return user

    @staticmethod
    def update_staff_user(
        *,
        staff_user: User,
        actor: User,
        validated_data: dict[str, Any],
        request: HttpRequest | None = None,
    ) -> User:
        if staff_user.role not in STAFF_ROLES:
            raise ValueError("Only clinical and reception staff can be managed here.")
        if staff_user.pk == actor.pk and not validated_data.get("is_active", True):
            raise ValueError("You cannot deactivate your own account.")

        password = validated_data.pop("password", None)
        role = validated_data.get("role", staff_user.role)
        if role not in STAFF_ROLES:
            raise ValueError("Invalid staff role.")

        clinic = validated_data.get("clinic")
        if not clinic:
            raise ValueError("Clinic is required for staff accounts.")

        with transaction.atomic():
            staff_user.first_name = validated_data.get("first_name", staff_user.first_name)
            staff_user.last_name = validated_data.get("last_name", staff_user.last_name)
            staff_user.role = role
            staff_user.clinic = clinic
            staff_user.is_active = validated_data.get("is_active", staff_user.is_active)
            staff_user.is_verified = validated_data.get("is_verified", staff_user.is_verified)
            if password:
                staff_user.set_password(password)
            staff_user.save()
            AuditService.log(
                action=AuditAction.UPDATE,
                object_type="User",
                object_id=str(staff_user.pk),
                user=actor,
                request=request,
                details={"email": staff_user.email, "role": staff_user.role},
            )
        return staff_user
