import json
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from consultations.ai_consultation import (
    ConsultationAIConfigurationError,
    ConsultationAISuggestion,
    build_clinical_context,
    generate_consultation_suggestion,
)
from triage.models import SeverityLevel, TriageRecord


@pytest.mark.django_db
class TestConsultAI:
    def test_build_clinical_context_includes_triage(self, assigned_patient, nurse):
        triage = TriageRecord.objects.create(
            patient=assigned_patient,
            nurse=nurse,
            blood_pressure="120/80",
            heart_rate=72,
            respiratory_rate=16,
            oxygen_saturation="98.0",
            body_temperature="36.6",
            symptoms="Fever and cough",
            severity_level=SeverityLevel.MODERATE,
            priority_score=5,
        )
        text = build_clinical_context(assigned_patient, triage)
        assert assigned_patient.patient_number in text
        assert "Fever and cough" in text
        assert "120/80" in text

    @patch("consultations.ai_consultation.config")
    def test_generate_requires_api_key(self, mock_config, assigned_patient):
        def _config(key, default="", cast=None):
            if key == "OPENAI_API_KEY":
                return ""
            return default

        mock_config.side_effect = _config
        with pytest.raises(ConsultationAIConfigurationError):
            generate_consultation_suggestion(assigned_patient, None)

    @patch("consultations.ai_consultation.httpx.Client")
    @patch("consultations.ai_consultation.config")
    def test_generate_parses_openai_response(
        self, mock_config, mock_client_cls, assigned_patient, nurse
    ):
        def _config(key, default="", cast=None):
            values = {
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_MODEL": "gpt-4o-mini",
                "OPENAI_TIMEOUT_SECONDS": 30,
            }
            val = values.get(key, default)
            return cast(val) if cast is not None and val != default else val

        mock_config.side_effect = _config

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "diagnosis": "Acute viral URI",
                                "treatment": "Supportive care",
                                "prescription": "Paracetamol 500mg q6h PRN",
                                "consultation_notes": "Return if worse. Physician to verify.",
                            }
                        )
                    }
                }
            ]
        }
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response

        triage = TriageRecord.objects.create(
            patient=assigned_patient,
            nurse=nurse,
            blood_pressure="120/80",
            heart_rate=72,
            respiratory_rate=16,
            oxygen_saturation="98.0",
            body_temperature="36.6",
            symptoms="Cough",
            severity_level=SeverityLevel.STABLE,
            priority_score=2,
        )
        result = generate_consultation_suggestion(assigned_patient, triage)
        assert isinstance(result, ConsultationAISuggestion)
        assert result.diagnosis == "Acute viral URI"

    @patch("dashboard.views.generate_consultation_suggestion")
    def test_doctor_ai_endpoint_returns_json(self, mock_generate, client, doctor, assigned_patient):
        mock_generate.return_value = ConsultationAISuggestion(
            diagnosis="Test dx",
            treatment="Test tx",
            prescription="Test rx",
            consultation_notes="Test notes",
        )
        client.force_login(doctor)
        response = client.post(
            reverse("dashboard:doctor-queue-consultation-ai"),
            {"patient_id": assigned_patient.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["diagnosis"] == "Test dx"
        assert "disclaimer" in data

    def test_nurse_cannot_use_ai_endpoint(self, client, nurse, assigned_patient):
        client.force_login(nurse)
        response = client.post(
            reverse("dashboard:doctor-queue-consultation-ai"),
            {"patient_id": assigned_patient.id},
        )
        assert response.status_code == 302

    @patch("dashboard.views.generate_consultation_suggestion")
    def test_consult_modal_includes_consult_ai_button(
        self, mock_generate, client, doctor, assigned_patient
    ):
        client.force_login(doctor)
        response = client.get(
            reverse("dashboard:doctor-queue-consultation-form"),
            {"patient": assigned_patient.id},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"Consult AI" in response.content
        mock_generate.assert_not_called()
