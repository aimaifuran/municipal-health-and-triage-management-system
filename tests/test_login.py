"""Login page validation and inline error display."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestLoginPage:
    url = reverse("accounts:login")

    def test_get_renders_sign_in_button(self, client):
        response = client.get(self.url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Sign In" in content
        assert 'id="login-btn-label"' in content
        assert "notify-alert-group" not in content

    def test_empty_submit_shows_field_errors_inline(self, client):
        response = client.post(self.url, {"username": "", "password": ""})
        assert response.status_code == 200
        content = response.content.decode()
        assert "form-input-error" in content
        assert "Email is required." in content
        assert "Password is required." in content
        assert "notify-alert-group" not in content

    def test_invalid_credentials_shows_message_in_card(self, client, doctor):
        response = client.post(
            self.url,
            {"username": doctor.email, "password": "wrong-password"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Invalid credentials" in content
        assert "login-credentials-error" in content
        assert "notify-alert-group" not in content

    def test_valid_login_redirects(self, client, doctor):
        response = client.post(
            self.url,
            {"username": doctor.email, "password": "SecurePass123!"},
        )
        assert response.status_code == 302

    def test_logout_flash_not_shown_on_login_card(self, client, doctor):
        client.force_login(doctor)
        client.post(reverse("accounts:logout"))
        response = client.get(self.url)
        content = response.content.decode()
        assert "notify-alert-group" not in content
