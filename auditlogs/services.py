"""Audit logging service layer."""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.http import HttpRequest

from auditlogs.models import AuditAction, AuditLog, LoginAttempt

User = get_user_model()
security_logger = logging.getLogger("security")
audit_logger = logging.getLogger("audit")


def _get_client_ip(request: HttpRequest | None) -> str | None:
    if not request:
        return None
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _get_user_agent(request: HttpRequest | None) -> str:
    if not request:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:512]


class AuditService:
    @staticmethod
    def log(
        action: str,
        object_type: str,
        object_id: str = "",
        user: User | None = None,
        request: HttpRequest | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        object_id_str = str(object_id) if object_id else ""
        max_length = AuditLog._meta.get_field("object_id").max_length or len(object_id_str)
        if len(object_id_str) > max_length:
            object_id_str = object_id_str[: max_length - 3] + "..." if max_length > 3 else object_id_str[:max_length]

        entry = AuditLog.objects.create(
            user=user,
            action=action,
            object_type=object_type,
            object_id=object_id_str,
            details=details or {},
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
        )
        audit_logger.info(
            "action=%s object_type=%s object_id=%s user=%s",
            action,
            object_type,
            object_id,
            getattr(user, "email", None),
        )
        if action in (
            AuditAction.UNAUTHORIZED_ACCESS,
            AuditAction.SECURITY_VIOLATION,
            AuditAction.LOGIN_FAILED,
        ):
            security_logger.warning(
                "SECURITY action=%s user=%s ip=%s",
                action,
                getattr(user, "email", None),
                _get_client_ip(request),
            )
        return entry

    @staticmethod
    def log_login_attempt(
        email: str,
        success: bool,
        request: HttpRequest | None = None,
    ) -> LoginAttempt:
        attempt = LoginAttempt.objects.create(
            email_attempted=email,
            ip_address=_get_client_ip(request) or "0.0.0.0",  # nosec B104
            success=success,
            user_agent=_get_user_agent(request),
        )
        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED
        AuditService.log(
            action=action,
            object_type="User",
            object_id=email,
            request=request,
            details={"success": success},
        )
        return attempt
