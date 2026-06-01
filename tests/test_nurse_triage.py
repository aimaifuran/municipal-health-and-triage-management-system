import pytest
from django.urls import reverse
from django.utils import timezone

from consultations.models import Consultation
from triage.models import TriageRecord


@pytest.mark.django_db
class TestNurseTriageDashboard:
    def test_nurse_dashboard_shows_triage_form(self, client, nurse):
        client.force_login(nurse)
        response = client.get(reverse("dashboard:home"))
        assert response.status_code == 200
        assert b"Record Vitals" in response.content
        assert b"Awaiting triage" in response.content or b"Select a patient" in response.content

    def test_nurse_dashboard_shows_discharged_patients(self, client, nurse, doctor, patient):
        client.force_login(nurse)
        Consultation.objects.create(
            patient=patient,
            doctor=doctor,
            admitted=True,
            discharged=True,
            discharged_at=timezone.now(),
        )
        response = client.get(reverse("dashboard:home"))
        assert response.status_code == 200
        assert b"Discharged Patients" in response.content
        assert patient.patient_number.encode() in response.content

    def test_nurse_can_create_triage(self, client, nurse, patient):
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
                "symptoms": "Mild headache and fatigue",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        record = TriageRecord.objects.get(patient=patient, is_active=True)
        assert record.nurse == nurse
        assert record.symptoms == "Mild headache and fatigue"
        assert record.priority_score >= 0

    def test_nurse_can_update_triage(self, client, nurse, patient):
        client.force_login(nurse)
        client.post(
            reverse("dashboard:nurse-triage-submit"),
            {
                "patient_id": str(patient.id),
                "blood_pressure": "120/80",
                "heart_rate": 72,
                "respiratory_rate": 16,
                "oxygen_saturation": "99.0",
                "body_temperature": "36.6",
                "symptoms": "Routine check",
            },
        )
        response = client.post(
            reverse("dashboard:nurse-triage-submit"),
            {
                "patient_id": str(patient.id),
                "blood_pressure": "190/110",
                "heart_rate": 130,
                "respiratory_rate": 24,
                "oxygen_saturation": "88.0",
                "body_temperature": "39.5",
                "symptoms": "Chest pain and difficulty breathing",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        record = TriageRecord.objects.get(patient=patient, is_active=True)
        assert record.priority_score >= 60
        assert record.severity_level == "critical"

    def test_nurse_can_register_patient(self, client, nurse):
        client.force_login(nurse)
        response = client.post(
            reverse("dashboard:nurse-patient-register"),
            {
                "first_name": "Ana",
                "middle_name": "",
                "last_name": "Reyes",
                "birth_date": "1985-06-12",
                "gender": "female",
                "address": "Cebu City",
                "contact_number": "+639171234567",
                "emergency_contact": "Pedro Reyes",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        from patients.models import Patient

        patient = Patient.objects.get(first_name="Ana", last_name="Reyes", clinic=nurse.clinic)
        assert patient.created_by == nurse
        assert patient.patient_number.startswith("PAT-")

    def test_receptionist_cannot_submit_triage(self, client, receptionist, patient):
        client.force_login(receptionist)
        response = client.post(
            reverse("dashboard:nurse-triage-submit"),
            {
                "patient_id": str(patient.id),
                "blood_pressure": "120/80",
                "heart_rate": 72,
                "respiratory_rate": 16,
                "oxygen_saturation": "98.0",
                "body_temperature": "36.6",
                "symptoms": "Test",
            },
        )
        assert response.status_code == 302
        assert TriageRecord.objects.filter(patient=patient, is_active=True).count() == 0
