"""Development settings."""

from .base import *  # noqa: F403

DEBUG = config("DEBUG", default=True, cast=bool)  # noqa: F405

if config("USE_SQLITE_DEV", default="0") == "1":  # noqa: F405
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

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INSTALLED_APPS += ["django_extensions"] if False else []  # noqa: F405

SECURE_SSL_REDIRECT = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
