"""Production settings — DEBUG is always False."""
from __future__ import annotations

import dj_database_url

from .base import *  # noqa: F403

DEBUG = False

database_url = config("DATABASE_URL", default="")  # noqa: F405
if database_url:
    DATABASES["default"] = dj_database_url.parse(database_url, conn_max_age=600, ssl_require=True)  # noqa: F405

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())  # noqa: F405

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://res.cloudinary.com; "
    "connect-src 'self' https://cdn.tailwindcss.com; "
    "frame-ancestors 'none';"
)
