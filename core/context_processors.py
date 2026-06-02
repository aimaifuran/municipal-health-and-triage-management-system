"""Global template context."""

from django.conf import settings


def global_context(request):
    return {
        "APP_NAME": "MHTMS",
        "APP_FULL_NAME": "Municipal Health & Triage Management System",
        "DEBUG": settings.DEBUG,
    }
