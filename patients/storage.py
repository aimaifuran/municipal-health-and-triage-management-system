"""Cloudinary upload helpers with validation."""
from __future__ import annotations

import cloudinary.uploader
from django.conf import settings
from django.core.exceptions import ValidationError

from common.cloudinary_utils import ensure_cloudinary_configured


def validate_upload(file) -> None:
    max_bytes = getattr(settings, "MAX_UPLOAD_SIZE_MB", 10) * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(f"File size must not exceed {settings.MAX_UPLOAD_SIZE_MB}MB.")
    allowed = {"image/jpeg", "image/png", "application/pdf"}
    if getattr(file, "content_type", None) not in allowed:
        raise ValidationError("Only JPEG, PNG, and PDF files are allowed.")


def upload_patient_document(file, folder: str = "mhtms/patients") -> dict:
    validate_upload(file)
    ensure_cloudinary_configured()
    return cloudinary.uploader.upload(
        file,
        folder=folder,
        resource_type="auto",
        unsigned=False,
    )
