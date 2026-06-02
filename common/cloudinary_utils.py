"""Configure Cloudinary SDK from Django settings (required for direct uploader calls)."""

from __future__ import annotations

import logging

import cloudinary
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

_CONFIGURED = False


def ensure_cloudinary_configured() -> None:
    """Apply CLOUDINARY_STORAGE credentials to the cloudinary Python SDK."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass

    storage = getattr(settings, "CLOUDINARY_STORAGE", {})
    cloud_name = (storage.get("CLOUD_NAME") or "").strip()
    api_key = (storage.get("API_KEY") or "").strip()
    api_secret = (storage.get("API_SECRET") or "").strip()

    if not cloud_name or not api_key or not api_secret:
        raise ValidationError(
            "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in your .env file."
        )

    if cloud_name == "demo" or api_key == "demo":
        raise ValidationError(
            "Cloudinary is using placeholder credentials. Add your real Cloudinary "
            "cloud name, API key, and API secret from https://console.cloudinary.com/"
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )
    _CONFIGURED = True
    logger.debug("Cloudinary SDK configured for cloud %s", cloud_name)
