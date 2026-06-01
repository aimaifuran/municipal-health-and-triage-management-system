"""Doctor bulk discharge UI wiring."""
import pytest
from django.urls import reverse


@pytest.fixture(autouse=True)
def simple_staticfiles(settings):
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.mark.django_db
class TestDoctorBulkDischargeUI:
    def test_doctor_dashboard_has_discharge_actions_and_page_level_modals(self, client, doctor):
        client.force_login(doctor)
        response = client.get(reverse("dashboard:home"))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'data-action="discharge-open"' in content
        assert 'data-action="discharge-confirm"' in content
        assert 'data-modal="discharge-confirm"' in content
        assert content.index('data-modal="discharge-confirm"') > content.index(
            'id="bulk-discharge-panel"'
        )
