"""Custom DRF exception handler."""
from __future__ import annotations

from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {
            "success": False,
            "error": response.data,
            "message": _human_message(response.status_code, response.data),
        }
    return response


def _human_message(status_code: int, data: Any) -> str:
    if status_code == 401:
        return "Session expired. Please login again."
    if status_code == 403:
        return "Unauthorized access detected."
    if status_code == 404:
        return "The requested resource was not found."
    if status_code == 400:
        return "Please correct the errors in your submission."
    if status_code >= 500:
        return "An unexpected error occurred. Please try again later."
    return "Request could not be processed."
