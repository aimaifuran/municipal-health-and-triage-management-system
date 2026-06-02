import pytest
from django.urls import reverse
from django.utils import timezone

from consultations.models import Consultation
from triage.models import SeverityLevel, TriageRecord


@pytest.fixture
def discharged_consultation(db, assigned_patient, doctor, nurse):
    triage = TriageRecord.objects.create(
        patient=assigned_patient,
        nurse=nurse,
        blood_pressure="120/80",
        heart_rate=72,
        respiratory_rate=16,
        oxygen_saturation="98.0",
        body_temperature="36.6",
        symptoms="Mild fever and cough",
        severity_level=SeverityLevel.MODERATE,
        priority_score=5,
    )
    consultation = Consultation.objects.create(
        patient=assigned_patient,
        doctor=doctor,
        diagnosis="Acute upper respiratory tract infection",
        treatment="Rest, fluids, symptomatic care",
        prescription="Paracetamol 500mg every 6 hours as needed for fever",
        admitted=True,
        discharged=True,
        discharged_at=timezone.now(),
        consultation_notes="Follow up if symptoms persist beyond 5 days.",
    )
    return consultation, triage


@pytest.mark.django_db
class TestDischargeSummary:
    def test_modal_includes_download_and_print(self, client, doctor, discharged_consultation):
        consultation, _ = discharged_consultation
        client.force_login(doctor)
        response = client.get(reverse("dashboard:doctor-discharged-detail", args=[consultation.id]))
        assert response.status_code == 200
        assert b"Download" in response.content
        assert b"Print" in response.content
        assert b"Close" in response.content
        assert b'data-action="close-discharged-detail"' in response.content
        assert (
            reverse("dashboard:doctor-discharged-summary-download", args=[consultation.id]).encode()
            in response.content
        )

    def test_doctor_can_download_pdf(self, client, doctor, discharged_consultation):
        consultation, _ = discharged_consultation
        client.force_login(doctor)
        url = reverse("dashboard:doctor-discharged-summary-download", args=[consultation.id])
        response = client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response.content[:4] == b"%PDF"
        assert "attachment" in response["Content-Disposition"]
        assert (
            consultation.patient.patient_number.replace("/", "-") in response["Content-Disposition"]
        )

    def test_nurse_can_download_pdf(self, client, nurse, discharged_consultation):
        consultation, _ = discharged_consultation
        client.force_login(nurse)
        response = client.get(
            reverse("dashboard:doctor-discharged-summary-download", args=[consultation.id])
        )
        assert response.status_code == 200
        assert response.content[:4] == b"%PDF"

    def test_print_view_renders_summary(self, client, doctor, discharged_consultation):
        consultation, _ = discharged_consultation
        client.force_login(doctor)
        response = client.get(
            reverse("dashboard:doctor-discharged-summary-print", args=[consultation.id])
        )
        assert response.status_code == 200
        assert b"OUTPATIENT DISCHARGE SUMMARY" in response.content
        assert consultation.diagnosis.encode() in response.content

    def test_receptionist_cannot_download(self, client, receptionist, discharged_consultation):
        consultation, _ = discharged_consultation
        client.force_login(receptionist)
        response = client.get(
            reverse("dashboard:doctor-discharged-summary-download", args=[consultation.id])
        )
        assert response.status_code == 302
        assert response.url.endswith(reverse("dashboard:unauthorized"))
