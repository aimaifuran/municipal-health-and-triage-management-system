"""DRF permission classes for RBAC and anti-IDOR."""
from __future__ import annotations

from typing import Any

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from accounts.models import UserRole


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.SUPER_ADMIN
        )


class IsDoctor(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (UserRole.DOCTOR, UserRole.SUPER_ADMIN)
        )


class IsNurse(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (UserRole.NURSE, UserRole.SUPER_ADMIN)
        )


class IsReceptionist(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (UserRole.RECEPTIONIST, UserRole.SUPER_ADMIN)
        )


class IsClinicalStaff(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role
            in (UserRole.DOCTOR, UserRole.NURSE, UserRole.SUPER_ADMIN)
        )


class DenyConsultationForReceptionist(permissions.BasePermission):
    """Receptionists cannot access consultation endpoints."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == UserRole.RECEPTIONIST:
            return False
        return True


class ClinicObjectPermission(permissions.BasePermission):
    """Object-level permission: resource must belong to user's clinic."""

    clinic_field = "clinic"

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role == UserRole.SUPER_ADMIN or user.is_superuser:
            return True
        clinic = getattr(obj, self.clinic_field, None)
        if clinic is None and hasattr(obj, "patient"):
            clinic = obj.patient.clinic
        if clinic is None and hasattr(obj, "clinic_id"):
            return str(obj.clinic_id) == str(user.clinic_id)
        return str(clinic.id) == str(user.clinic_id)
