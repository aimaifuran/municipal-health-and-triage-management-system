"""Doctor bulk discharge UI wiring."""

import pytest
from django.urls import reverse

from consultations.models import Consultation


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

    def test_dashboard_bulk_discharge_posts_multiple_selected_patients(
        self, client, doctor, assigned_patient
    ):
        c1 = Consultation.objects.create(
            patient=assigned_patient,
            doctor=doctor,
            diagnosis="Flu",
            treatment="Rest",
            admitted=True,
        )
        c2 = Consultation.objects.create(
            patient=assigned_patient,
            doctor=doctor,
            diagnosis="Cold",
            treatment="Fluids",
            admitted=True,
        )
        client.force_login(doctor)

        response = client.post(
            reverse("dashboard:bulk-discharge"),
            {"consultation_ids": [str(c1.id), str(c2.id)]},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        c1.refresh_from_db()
        c2.refresh_from_db()
        assert c1.discharged is True
        assert c2.discharged is True

    def test_dashboard_bulk_discharge_accepts_comma_joined_multiple_ids(
        self, client, doctor, assigned_patient
    ):
        c1 = Consultation.objects.create(
            patient=assigned_patient,
            doctor=doctor,
            diagnosis="Flu",
            treatment="Rest",
            admitted=True,
        )
        c2 = Consultation.objects.create(
            patient=assigned_patient,
            doctor=doctor,
            diagnosis="Cold",
            treatment="Fluids",
            admitted=True,
        )
        client.force_login(doctor)

        response = client.post(
            reverse("dashboard:bulk-discharge"),
            {"consultation_ids": f"{c1.id},{c2.id}"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        c1.refresh_from_db()
        c2.refresh_from_db()
        assert c1.discharged is True
        assert c2.discharged is True
