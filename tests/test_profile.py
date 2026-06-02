from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import User

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@pytest.fixture(autouse=True)
def simple_static_storage():
    with override_settings(STORAGES=TEST_STORAGES):
        yield


@pytest.mark.django_db
class TestProfile:
    def test_profile_page_requires_login(self, client):
        response = client.get(reverse("accounts:profile"))
        assert response.status_code == 302
        assert "login" in response.url

    def test_profile_page_loads(self, client, doctor):
        client.force_login(doctor)
        response = client.get(reverse("accounts:profile"))
        assert response.status_code == 200
        assert b"My Profile" in response.content
        assert b"Change password" in response.content

    def test_update_details(self, client, doctor):
        client.force_login(doctor)
        response = client.post(
            reverse("accounts:profile"),
            {
                "action": "details",
                "first_name": "Maria",
                "last_name": "Santos",
                "email": doctor.email,
            },
        )
        assert response.status_code == 302
        doctor.refresh_from_db()
        assert doctor.first_name == "Maria"
        assert doctor.last_name == "Santos"

    def test_change_password(self, client, doctor):
        client.force_login(doctor)
        response = client.post(
            reverse("accounts:profile"),
            {
                "action": "password",
                "old_password": "SecurePass123!",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            },
        )
        assert response.status_code == 302
        doctor.refresh_from_db()
        assert doctor.check_password("NewSecurePass123!")

    @patch("accounts.profile_service.upload_profile_picture")
    def test_upload_profile_picture(self, mock_upload, doctor):
        from accounts.profile_service import ProfileService

        mock_upload.return_value = {
            "public_id": "mhtms/profiles/test/avatar",
            "secure_url": "https://res.cloudinary.com/demo/image/upload/v1/avatar.jpg",
        }
        buffer = BytesIO()
        Image.new("RGB", (8, 8), color="teal").save(buffer, format="PNG")
        buffer.seek(0)
        image = SimpleUploadedFile("avatar.png", buffer.read(), content_type="image/png")

        ProfileService.update_picture(user=doctor, uploaded_file=image)
        doctor.refresh_from_db()

        mock_upload.assert_called_once()
        assert "cloudinary.com" in doctor.profile_picture_url
        assert doctor.profile_picture_public_id == "mhtms/profiles/test/avatar"

    def test_email_unique_validation(self, client, doctor, nurse):
        client.force_login(doctor)
        response = client.post(
            reverse("accounts:profile"),
            {
                "action": "details",
                "first_name": "Test",
                "last_name": "Doctor",
                "email": nurse.email,
            },
        )
        assert response.status_code == 302
        doctor.refresh_from_db()
        assert doctor.email != nurse.email
