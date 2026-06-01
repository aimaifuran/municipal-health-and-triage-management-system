"""Audit and security event logging."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    CREATE = "create", "Create"
    UPDATE = "update", "Update"
    DELETE = "delete", "Delete"
    ARCHIVE = "archive", "Archive"
    LOGIN = "login", "Login"
    LOGOUT = "logout", "Logout"
    LOGIN_FAILED = "login_failed", "Login Failed"
    BULK_DISCHARGE = "bulk_discharge", "Bulk Discharge"
    ADMIT = "admit", "Admit"
    DISCHARGE = "discharge", "Discharge"
    UNAUTHORIZED_ACCESS = "unauthorized_access", "Unauthorized Access"
    API_ACCESS = "api_access", "API Access"
    SECURITY_VIOLATION = "security_violation", "Security Violation"


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64, choices=AuditAction.choices, db_index=True)
    object_type = models.CharField(max_length=128, db_index=True)
    object_id = models.CharField(max_length=64, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["object_type", "object_id"]),
        ]


class LoginAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email_attempted = models.EmailField(db_index=True)
    ip_address = models.GenericIPAddressField()
    success = models.BooleanField(default=False)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["email_attempted", "success", "timestamp"]),
        ]
