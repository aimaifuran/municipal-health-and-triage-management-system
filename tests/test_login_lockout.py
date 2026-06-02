"""Login lockout: 5 failures → lock; correct password blocked; unlock after cooloff."""

from datetime import timedelta

import pytest
from axes.models import AccessAttempt
from django.urls import reverse
from django.utils import timezone


@pytest.fixture(autouse=True)
def simple_staticfiles(settings):
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture(autouse=True)
def lockout_policy(settings):
    settings.AXES_FAILURE_LIMIT = 5
    settings.AXES_COOLOFF_MINUTES = 10
    settings.AXES_COOLOFF_TIME = timedelta(minutes=10)
    settings.AXES_COOLOFF_MESSAGE = (
        "Account locked after 5 failed login attempts. "
        "Please try again in 10 minutes or contact an administrator."
    )


@pytest.fixture(autouse=True)
def clear_axes_attempts():
    AccessAttempt.objects.all().delete()
    yield
    AccessAttempt.objects.all().delete()


@pytest.mark.django_db
class TestLoginLockout:
    url = reverse("accounts:login")
    limit = 5

    def _fail_login(self, client, email: str):
        return client.post(
            self.url,
            {"username": email, "password": "wrong-password"},
        )

    def _lock_account(self, client, email: str):
        for _ in range(self.limit):
            self._fail_login(client, email)

    def test_locks_out_on_fifth_failed_attempt(self, client, doctor):
        for _ in range(self.limit - 1):
            response = self._fail_login(client, doctor.email)
            assert response.status_code == 200
            assert "Invalid credentials" in response.content.decode()

        response = self._fail_login(client, doctor.email)
        content = response.content.decode()
        assert response.status_code in (200, 429)
        assert "account locked" in content.lower()
        assert "10 minutes" in content.lower()
        assert content.lower().count("account locked after") == 1

        doctor.refresh_from_db()
        assert doctor.failed_login_attempts >= self.limit

    def test_locked_user_cannot_login_with_correct_password(self, client, doctor):
        self._lock_account(client, doctor.email)

        response = client.post(
            self.url,
            {"username": doctor.email, "password": "SecurePass123!"},
        )
        content = response.content.decode()
        assert response.status_code in (200, 429)
        assert "account locked" in content.lower()
        assert content.lower().count("account locked after") == 1
        assert client.session.get("_auth_user_id") is None

    def test_locked_user_cannot_login_from_different_ip(self, client, doctor):
        self._lock_account(client, doctor.email)

        client.defaults["REMOTE_ADDR"] = "10.0.0.99"
        response = client.post(
            self.url,
            {"username": doctor.email, "password": "SecurePass123!"},
        )
        content = response.content.decode()
        assert response.status_code in (200, 429)
        assert "account locked" in content.lower()
        assert client.session.get("_auth_user_id") is None

    def test_unlocks_after_cooloff_and_accepts_correct_password(self, client, doctor):
        self._lock_account(client, doctor.email)

        locked = client.post(
            self.url,
            {"username": doctor.email, "password": "SecurePass123!"},
        )
        assert client.session.get("_auth_user_id") is None
        assert "account locked" in locked.content.decode().lower()

        AccessAttempt.objects.filter(username__iexact=doctor.email).update(
            attempt_time=timezone.now() - timedelta(minutes=11)
        )

        response = client.post(
            self.url,
            {"username": doctor.email, "password": "SecurePass123!"},
        )
        assert response.status_code == 302
        assert client.session.get("_auth_user_id") is not None

        doctor.refresh_from_db()
        assert doctor.failed_login_attempts == 0

    def test_successful_login_resets_failed_counter(self, client, doctor):
        for _ in range(2):
            self._fail_login(client, doctor.email)

        doctor.refresh_from_db()
        assert doctor.failed_login_attempts == 2

        response = client.post(
            self.url,
            {"username": doctor.email, "password": "SecurePass123!"},
        )
        assert response.status_code == 302
        doctor.refresh_from_db()
        assert doctor.failed_login_attempts == 0
        assert AccessAttempt.objects.count() == 0
