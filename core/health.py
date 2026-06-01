"""Lightweight health checks for load balancers (Render, etc.)."""
from __future__ import annotations

from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """Return 200 when the app and database are reachable."""
    try:
        connection.ensure_connection()
    except Exception as exc:
        return JsonResponse(
            {"status": "error", "database": str(exc)},
            status=503,
        )
    return JsonResponse({"status": "ok"})


def health_live(request):
    """Liveness probe — process is up (no database check)."""
    return JsonResponse({"status": "ok"})
