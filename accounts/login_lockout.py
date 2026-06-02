"""Login lockout helpers (django-axes + per-user failed attempt counter)."""

from __future__ import annotations

from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_lockout_message
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

User = get_user_model()


def normalize_login_username(username: str) -> str:
    return (username or "").strip().lower()


def is_login_locked(
    request: HttpRequest,
    username: str,
    attempted_password: str | None = None,
) -> bool:
    """
    Return True if login must be rejected (including correct passwords while locked).

    Lockout is enforced per account email (see AXES_LOCKOUT_PARAMETERS), not per IP alone.
    """
    email = normalize_login_username(username)
    if not email:
        return False
    credentials = {"username": email, "password": attempted_password or ""}
    return not AxesProxyHandler.is_allowed(request, credentials)


def record_failed_login(username: str) -> None:
    """Increment failed attempts for an existing account (audit/admin visibility)."""
    email = normalize_login_username(username)
    if not email:
        return
    user = User.objects.filter(email__iexact=email).first()
    if user:
        user.increment_failed_login()


def axes_lockout_response(
    request: HttpRequest,
    response: HttpResponse | None = None,
    credentials: dict | None = None,
) -> HttpResponse:
    """Render the login page with a lockout message (used by django-axes middleware)."""
    from accounts.forms import LoginForm

    # Show lockout via context only — avoid duplicating form.non_field_errors from the view.
    form = LoginForm(request=request, data=request.POST or None)
    return render(
        request,
        "accounts/login.html",
        {"form": form, "lockout_message": get_lockout_message()},
        status=429,
    )
