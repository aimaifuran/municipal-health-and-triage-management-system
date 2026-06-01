"""Security headers and audit middleware."""
from __future__ import annotations

from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from auditlogs.models import AuditAction
from auditlogs.services import AuditService


class SecurityHeadersMiddleware:
    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        csp = getattr(settings, "CONTENT_SECURITY_POLICY", None)
        if csp:
            response["Content-Security-Policy"] = csp
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = getattr(settings, "SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin")
        return response


class AuditMiddleware:
    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if response.status_code == 403 and request.user.is_authenticated:
            AuditService.log(
                action=AuditAction.UNAUTHORIZED_ACCESS,
                object_type="HTTP",
                object_id=request.path,
                user=request.user,
                request=request,
            )
        return response
