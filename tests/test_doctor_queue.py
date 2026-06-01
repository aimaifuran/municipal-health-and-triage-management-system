import pytest
from django.urls import reverse

from accounts.models import DoctorPatientAssignment
from triage.models import TriageRecord


@pytest.mark.django_db
class TestDoctorQueueAfterTriage:
    def test_doctor_sees_patient_after_nurse_triage_without_prior_assignment(
        self, client, nurse, doctor, patient
    ):
        assert not DoctorPatientAssignment.objects.filter(doctor=doctor, patient=patient).exists()

        client.force_login(nurse)
        response = client.post(
            reverse("dashboard:nurse-triage-submit"),
            {
                "patient_id": str(patient.id),
                "blood_pressure": "118/76",
                "heart_rate": 78,
                "respiratory_rate": 16,
                "oxygen_saturation": "98.0",
                "body_temperature": "36.8",
                "symptoms": "Mild headache",
            },
        )
        assert response.status_code == 200
        assert DoctorPatientAssignment.objects.filter(
            doctor=doctor, patient=patient, is_active=True
        ).exists()
        assert TriageRecord.objects.filter(patient=patient, is_active=True).exists()

        client.force_login(doctor)
        dashboard = client.get(reverse("dashboard:home"))
        assert dashboard.status_code == 200
        assert patient.patient_number.encode() in dashboard.content
        assert patient.full_name.encode() in dashboard.content
