"""Development settings."""
import os

from .base import *  # noqa: F403

DEBUG = config("DEBUG", default=True, cast=bool)  # noqa: F405

if os.environ.get("USE_SQLITE_DEV") == "1":
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        }
    }

CACHES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Shorter lockout during local development (production uses 1 hour from base settings)
AXES_COOLOFF_TIME = 1  # noqa: F405
AXES_FAILURE_LIMIT = 10  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INSTALLED_APPS += ["django_extensions"] if False else []  # noqa: F405

SECURE_SSL_REDIRECT = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
