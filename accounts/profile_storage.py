"""Cloudinary helpers for staff profile pictures."""

from __future__ import annotations

import logging

import cloudinary.uploader
from django.conf import settings
from django.core.exceptions import ValidationError

from common.cloudinary_utils import ensure_cloudinary_configured

logger = logging.getLogger(__name__)

PROFILE_MAX_MB = 5
PROFILE_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_profile_image(file) -> None:
    max_bytes = PROFILE_MAX_MB * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(f"Profile image must not exceed {PROFILE_MAX_MB}MB.")
    content_type = getattr(file, "content_type", None)
    if content_type not in PROFILE_ALLOWED_TYPES:
        raise ValidationError("Profile picture must be JPEG, PNG, or WebP.")


def upload_profile_picture(file, *, user_id: str) -> dict:
    validate_profile_image(file)
    ensure_cloudinary_configured()
    folder = getattr(settings, "CLOUDINARY_PROFILE_FOLDER", "mhtms/profiles")
    return cloudinary.uploader.upload(
        file,
        folder=f"{folder}/{user_id}",
        resource_type="image",
        overwrite=True,
        transformation=[
            {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
            {"quality": "auto", "fetch_format": "auto"},
        ],
    )


def delete_profile_picture(public_id: str) -> None:
    if not public_id:
        return
    try:
        ensure_cloudinary_configured()
        cloudinary.uploader.destroy(public_id, resource_type="image")
    except Exception as exc:
        logger.warning("Cloudinary delete failed for %s: %s", public_id, exc)
