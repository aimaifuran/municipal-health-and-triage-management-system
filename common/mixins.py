"""Reusable view and permission mixins."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from accounts.models import UserRole


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles: tuple[str, ...] = ()

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.allowed_roles and request.user.role not in self.allowed_roles:
            return redirect("dashboard:unauthorized")
        return super().dispatch(request, *args, **kwargs)


class SuperAdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = (UserRole.SUPER_ADMIN,)


class DoctorRequiredMixin(RoleRequiredMixin):
    allowed_roles = (UserRole.DOCTOR, UserRole.SUPER_ADMIN)


class NurseRequiredMixin(RoleRequiredMixin):
    allowed_roles = (UserRole.NURSE, UserRole.SUPER_ADMIN)


class ReceptionistRequiredMixin(RoleRequiredMixin):
    allowed_roles = (UserRole.RECEPTIONIST, UserRole.SUPER_ADMIN)


class ClinicScopedMixin:
    """Filter querysets to the user's clinic unless super admin."""

    def get_clinic_filter_kwargs(self) -> dict[str, Any]:
        user = self.request.user
        if user.is_superuser or user.role == UserRole.SUPER_ADMIN:
            return {}
        if user.clinic_id:
            return {"clinic_id": user.clinic_id}
        return {"clinic_id": None}
