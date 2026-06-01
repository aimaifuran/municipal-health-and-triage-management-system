import pytest
from django.urls import reverse

from consultations.models import Consultation
from consultations.services import ConsultationService
from triage.models import TriageRecord
from triage.services import TriageService


@pytest.mark.django_db
class TestDoctorQueueConsultation:
    def test_save_and_admit_from_queue(self, client, doctor, assigned_patient, nurse):
        TriageService.create_triage(
            patient=assigned_patient,
            nurse=nurse,
            validated_data={
                "blood_pressure": "120/80",
                "heart_rate": 72,
                "respiratory_rate": 16,
                "oxygen_saturation": "98",
                "body_temperature": "36.6",
                "symptoms": "Fever",
            },
        )
        client.force_login(doctor)
        url = reverse("dashboard:doctor-queue-consultation-submit")
        response = client.post(
            url,
            {
                "patient_id": assigned_patient.id,
                "action": "admit",
                "diagnosis": "Viral URI",
                "treatment": "Fluids and rest",
                "prescription": "",
                "consultation_notes": "Follow up in 3 days",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        consultation = Consultation.objects.get(patient=assigned_patient, doctor=doctor)
        assert consultation.admitted is True
        assert consultation.diagnosis == "Viral URI"
        assert consultation.discharged is False

    def test_save_without_admit(self, client, doctor, assigned_patient):
        client.force_login(doctor)
        url = reverse("dashboard:doctor-queue-consultation-submit")
        response = client.post(
            url,
            {
                "patient_id": assigned_patient.id,
                "action": "save",
                "diagnosis": "Hypertension",
                "treatment": "Lifestyle changes",
                "prescription": "",
                "consultation_notes": "",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        consultation = ConsultationService.get_open_consultation(assigned_patient, doctor)
        assert consultation is not None
        assert consultation.admitted is False

    def test_consultation_form_requires_fields(self, client, doctor, assigned_patient):
        client.force_login(doctor)
        url = reverse("dashboard:doctor-queue-consultation-submit")
        response = client.post(
            url,
            {
                "patient_id": assigned_patient.id,
                "action": "save",
                "diagnosis": "",
                "treatment": "",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 400
        assert Consultation.objects.filter(patient=assigned_patient, doctor=doctor).count() == 0
