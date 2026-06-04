from datetime import date

import pytest
from rest_framework import status

from accounts.models import UserRole
from patients.models import Patient
from triage.services import TriageService


@pytest.mark.django_db
class TestAntiIDOR:
    def test_doctor_cannot_access_unassigned_patient(
        self, api_client, doctor, clinic, receptionist
    ):
        other = Patient.objects.create(
            patient_number="PAT-OTHER-001",
            first_name="Ana",
            last_name="Reyes",
            birth_date=date(1985, 5, 20),
            gender="female",
            address="Cebu",
            contact_number="+639171234568",
            emergency_contact="Pedro Reyes",
            clinic=clinic,
            created_by=receptionist,
        )
        api_client.force_authenticate(user=doctor)
        response = api_client.get(f"/api/v1/patients/{other.id}/")
        # 404 prevents patient ID enumeration (anti-IDOR)
        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)

    def test_doctor_can_access_assigned_patient(self, api_client, doctor, assigned_patient):
        api_client.force_authenticate(user=doctor)
        response = api_client.get(f"/api/v1/patients/{assigned_patient.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_receptionist_cannot_access_consultations(self, api_client, receptionist):
        api_client.force_authenticate(user=receptionist)
        response = api_client.get("/api/v1/consultations/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestPublicMaskedAPI:
    def test_public_api_masks_phi(self, api_client):
        response = api_client.get("/api/v1/public/health-stats/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["patient_name"] == "HIPAA Restricted"
        assert data["patient_details"] == "HIPAA Restricted"
        assert data["data_classification"] == "public_masked"
        assert data["sample_cases"] == []
        assert "first_name" not in data


@pytest.mark.django_db
class TestHealthStatsMaskingTwist:
    """Same report shape — clinical JWT unmasked vs API consumer / public masked."""

    def test_doctor_gets_unmasked_health_stats(
        self, api_client, doctor, assigned_patient, nurse
    ):
        TriageService.create_triage(
            patient=assigned_patient,
            nurse=nurse,
            validated_data={
                "blood_pressure": "180/110",
                "heart_rate": 110,
                "respiratory_rate": 24,
                "oxygen_saturation": "88",
                "body_temperature": "39.0",
                "symptoms": "Chest pain",
            },
        )
        api_client.force_authenticate(user=doctor)
        response = api_client.get("/api/v1/analytics/health-stats/?region=Region VII")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data_classification"] == "clinical_full"
        assert data["patient_name"] != "HIPAA Restricted"
        assert "Juan" in data["patient_name"]
        assert len(data["sample_cases"]) >= 1

    def test_api_consumer_gets_masked_health_stats(self, api_client, db):
        from accounts.models import User

        consumer = User.objects.create_user(
            email="api@test.gov.ph",
            password="SecurePass123!",
            role=UserRole.API_CONSUMER,
            is_verified=True,
        )
        api_client.force_authenticate(user=consumer)
        response = api_client.get("/api/v1/analytics/health-stats/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data_classification"] == "public_masked"
        assert data["patient_name"] == "HIPAA Restricted"
        assert data["sample_cases"] == []


@pytest.mark.django_db
class TestJWTAuth:
    def test_login_returns_tokens(self, api_client, doctor):
        response = api_client.post(
            "/api/v1/auth/login/",
            {"email": doctor.email, "password": "SecurePass123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
