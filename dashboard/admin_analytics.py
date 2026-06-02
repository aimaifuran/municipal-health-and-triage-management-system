"""Aggregate metrics and chart payloads for the super-admin dashboard."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.models import Clinic, User, UserRole
from accounts.services import STAFF_ROLES
from auditlogs.models import LoginAttempt
from patients.models import Patient
from triage.models import SeverityLevel, TriageRecord


def _last_n_days_labels(n: int = 7) -> list[str]:
    today = timezone.localdate()
    return [(today - timedelta(days=i)).strftime("%b %d") for i in range(n - 1, -1, -1)]


def _series_for_days(qs, date_field: str, days: int = 7) -> list[int]:
    """Count rows per calendar day for the last `days` days (inclusive)."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    rows = (
        qs.filter(**{f"{date_field}__date__gte": start})
        .annotate(day=TruncDate(date_field))
        .values("day")
        .annotate(count=Count("id"))
    )
    by_day = {row["day"]: row["count"] for row in rows}
    return [by_day.get(start + timedelta(days=i), 0) for i in range(days)]


def build_admin_dashboard_analytics() -> dict:
    queue_qs = TriageRecord.objects.filter(is_active=True).select_related("patient__clinic")
    day_labels = _last_n_days_labels(7)

    severity_map = {level.value: 0 for level in SeverityLevel}
    for row in queue_qs.values("severity_level").annotate(count=Count("id")):
        severity_map[row["severity_level"]] = row["count"]

    staff_map = {role: 0 for role in STAFF_ROLES}
    for row in (
        User.objects.filter(role__in=STAFF_ROLES, is_active=True)
        .values("role")
        .annotate(count=Count("id"))
    ):
        staff_map[row["role"]] = row["count"]

    clinic_rows = (
        queue_qs.values("patient__clinic__name").annotate(count=Count("id")).order_by("-count")[:8]
    )
    clinic_labels = [row["patient__clinic__name"] or "Unassigned" for row in clinic_rows]
    clinic_counts = [row["count"] for row in clinic_rows]

    patients_series = _series_for_days(Patient.objects.all(), "created_at", 7)

    login_qs = LoginAttempt.objects.filter(
        timestamp__date__gte=timezone.localdate() - timedelta(days=6)
    )
    login_success = _series_for_days(login_qs.filter(success=True), "timestamp", 7)
    login_failed = _series_for_days(login_qs.filter(success=False), "timestamp", 7)

    active_clinics = Clinic.objects.filter(is_active=True).count()
    total_staff = sum(staff_map.values())
    critical = severity_map.get(SeverityLevel.CRITICAL, 0)
    moderate = severity_map.get(SeverityLevel.MODERATE, 0)
    stable = severity_map.get(SeverityLevel.STABLE, 0)
    active_cases = sum(severity_map.values())

    return {
        "stats": {
            "clinic_count": active_clinics,
            "active_cases": active_cases,
            "critical": critical,
            "moderate": moderate,
            "stable": stable,
            "total_staff": total_staff,
            "total_patients": Patient.objects.count(),
            "failed_logins_24h": LoginAttempt.objects.filter(
                success=False,
                timestamp__gte=timezone.now() - timedelta(hours=24),
            ).count(),
        },
        "charts": {
            "day_labels": day_labels,
            "severity": {
                "labels": ["Critical", "Moderate", "Stable"],
                "values": [critical, moderate, stable],
                "colors": ["#dc2626", "#ca8a04", "#16a34a"],
            },
            "staff": {
                "labels": ["Doctors", "Nurses", "Receptionists"],
                "values": [
                    staff_map.get(UserRole.DOCTOR, 0),
                    staff_map.get(UserRole.NURSE, 0),
                    staff_map.get(UserRole.RECEPTIONIST, 0),
                ],
                "colors": ["#0284c7", "#0d9488", "#d97706"],
            },
            "clinic_triage": {
                "labels": clinic_labels,
                "values": clinic_counts,
            },
            "patients_daily": {
                "labels": day_labels,
                "values": patients_series,
            },
            "logins_daily": {
                "labels": day_labels,
                "success": login_success,
                "failed": login_failed,
            },
        },
    }
