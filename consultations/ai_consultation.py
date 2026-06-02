"""OpenAI-assisted consultation draft generation for doctor queue."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from decouple import config
from django.utils import timezone

from consultations.models import Consultation
from patients.models import Patient
from triage.models import TriageRecord

logger = logging.getLogger(__name__)

_SSL_CONFIGURED = False


def _configure_ssl() -> None:
    """Use OS trust store on Windows/macOS (fixes CERTIFICATE_VERIFY_FAILED)."""
    global _SSL_CONFIGURED
    if _SSL_CONFIGURED:
        return
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass
    _SSL_CONFIGURED = True


OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
REQUIRED_RESPONSE_KEYS = ("diagnosis", "treatment", "prescription", "consultation_notes")


class ConsultationAIError(Exception):
    """Base error for consultation AI failures."""


class ConsultationAIConfigurationError(ConsultationAIError):
    """Missing or invalid OpenAI configuration."""


class ConsultationAIRequestError(ConsultationAIError):
    """OpenAI API returned an error."""


class ConsultationAIResponseError(ConsultationAIError):
    """Could not parse or validate the model response."""


@dataclass(frozen=True)
class ConsultationAISuggestion:
    diagnosis: str
    treatment: str
    prescription: str
    consultation_notes: str

    def as_dict(self) -> dict[str, str]:
        return {
            "diagnosis": self.diagnosis,
            "treatment": self.treatment,
            "prescription": self.prescription,
            "consultation_notes": self.consultation_notes,
        }


def _coerce_birth_date(birth_date: date | str) -> date:
    if isinstance(birth_date, str):
        return date.fromisoformat(birth_date)
    return birth_date


def _patient_age_years(birth_date: date | str) -> int:
    birth_date = _coerce_birth_date(birth_date)
    today = timezone.localdate()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def build_clinical_context(
    patient: Patient,
    triage: TriageRecord | None,
    consultation: Consultation | None = None,
) -> str:
    """Structured clinical facts for the model (no instructions)."""
    lines = [
        f"Patient ID: {patient.patient_number}",
        f"Name: {patient.full_name}",
        f"Age: {_patient_age_years(patient.birth_date)} years",
        f"Sex: {patient.get_gender_display()}",
        f"Date of birth: {_coerce_birth_date(patient.birth_date).isoformat()}",
        f"Clinic: {patient.clinic.name} ({patient.clinic.municipality}, {patient.clinic.region})",
        f"Contact: {patient.contact_number}",
        f"Address: {patient.address}",
    ]
    if triage:
        triage_time = timezone.localtime(triage.created_at).strftime("%Y-%m-%d %H:%M %Z")
        lines.extend(
            [
                "",
                "=== Active triage (nurse-recorded) ===",
                f"Triage time: {triage_time}",
                f"Severity: {triage.get_severity_level_display()}",
                f"Priority score: {triage.priority_score}",
                f"Triage status: {triage.get_triage_status_display()}",
                f"Blood pressure: {triage.blood_pressure} mmHg",
                f"Heart rate: {triage.heart_rate} bpm",
                f"Respiratory rate: {triage.respiratory_rate} /min",
                f"SpO2: {triage.oxygen_saturation}%",
                f"Temperature: {triage.body_temperature} °C",
                f"Chief complaint / symptoms: {triage.symptoms}",
            ]
        )
        if triage.nurse_id:
            lines.append(f"Triaged by: {triage.nurse.full_name}")
    else:
        lines.extend(["", "=== Triage ===", "No active triage record on file."])

    if consultation:
        lines.extend(["", "=== Existing consultation draft (doctor may be editing) ==="])
        if consultation.diagnosis:
            lines.append(f"Current diagnosis: {consultation.diagnosis}")
        if consultation.treatment:
            lines.append(f"Current treatment: {consultation.treatment}")
        if consultation.prescription:
            lines.append(f"Current prescription: {consultation.prescription}")
        if consultation.consultation_notes:
            lines.append(f"Current notes: {consultation.consultation_notes}")

    return "\n".join(lines)


SYSTEM_PROMPT = """You are a clinical documentation assistant for licensed physicians working in \
Philippine municipal health centers (Rural Health Units / city health offices) under the Department of Health.

Your role is to propose DRAFT outpatient consultation documentation that the attending physician will \
review, edit, and take full responsibility for before it becomes part of the medical record.

Rules you MUST follow:
1. Base all reasoning ONLY on the clinical data provided. Do not invent labs, imaging, or history not given.
2. If data is insufficient for a definitive diagnosis, state the most likely working diagnosis and list \
key differentials briefly in the diagnosis field; note what additional history or exam would be needed in consultation_notes.
3. Align urgency with triage severity and vital signs. Flag red flags and emergency referral criteria when vitals or symptoms warrant it.
4. Treatment must be appropriate for a primary-care / municipal clinic scope in the Philippines (evidence-informed, practical).
5. Prescription: use generic drug names where possible; include dose, route, frequency, and duration; \
use medicines commonly available in Philippine public health facilities when reasonable. Leave prescription as an empty string only if no medication is indicated.
6. Use clear, professional medical English suitable for a legal medical record. Avoid markdown.
7. Do NOT claim to have examined the patient. Phrase as clinical impression based on available data.
8. consultation_notes must include: follow-up timing, warning signs for return/ER, brief patient education, \
and an explicit line that this draft requires physician verification.
9. If vitals suggest emergency (e.g., critical triage, dangerous BP/SpO2/temp), say so prominently and recommend immediate escalation/referral in treatment and notes.

Respond with a single JSON object only, matching this exact schema (all string values):
{
  "diagnosis": "Primary impression; include pertinent negatives or differentials when appropriate",
  "treatment": "Non-pharmacologic and pharmacologic plan; procedures if any",
  "prescription": "Medications with dosing, or empty string if none",
  "consultation_notes": "Follow-up, red flags, patient advice, physician verification reminder"
}"""


def _parse_model_json(content: str) -> ConsultationAISuggestion:
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConsultationAIResponseError("AI returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise ConsultationAIResponseError("AI response was not a JSON object.")
    missing = [key for key in REQUIRED_RESPONSE_KEYS if key not in payload]
    if missing:
        raise ConsultationAIResponseError(f"AI response missing fields: {', '.join(missing)}")
    cleaned = {}
    for key in REQUIRED_RESPONSE_KEYS:
        value = payload[key]
        if value is None:
            cleaned[key] = ""
        elif not isinstance(value, str):
            cleaned[key] = str(value).strip()
        else:
            cleaned[key] = value.strip()
    if not cleaned["diagnosis"] or not cleaned["treatment"]:
        raise ConsultationAIResponseError("Diagnosis and treatment are required in the AI draft.")
    return ConsultationAISuggestion(**cleaned)


def generate_consultation_suggestion(
    patient: Patient,
    triage: TriageRecord | None,
    consultation: Consultation | None = None,
) -> ConsultationAISuggestion:
    api_key = config("OPENAI_API_KEY", default="").strip()
    if not api_key:
        raise ConsultationAIConfigurationError(
            "OpenAI API key is not configured. Set OPENAI_API_KEY in your environment."
        )

    model = config("OPENAI_MODEL", default="gpt-4o-mini").strip()
    timeout = config("OPENAI_TIMEOUT_SECONDS", default=60, cast=int)
    clinical_context = build_clinical_context(patient, triage, consultation)

    user_message = (
        "Generate a draft outpatient consultation for the following patient. "
        "Use Philippine municipal health center standards. Return JSON only.\n\n"
        f"{clinical_context}"
    )

    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }

    _configure_ssl()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                OPENAI_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
    except httpx.TimeoutException as exc:
        raise ConsultationAIRequestError("OpenAI request timed out. Try again.") from exc
    except httpx.ConnectError as exc:
        logger.warning("OpenAI connection error: %s", exc)
        detail = str(exc).lower()
        if "certificate" in detail or "ssl" in detail:
            raise ConsultationAIRequestError(
                "SSL certificate verification failed when connecting to OpenAI. "
                "Run: pip install -r requirements/base.txt then restart the Django server. "
                "See docs/CONSULT_AI_SETUP.md (SSL on Windows)."
            ) from exc
        raise ConsultationAIRequestError(
            "Could not connect to OpenAI. Check your internet connection, firewall, or VPN."
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("OpenAI HTTP error: %s", exc)
        raise ConsultationAIRequestError(
            "Could not reach OpenAI. Check your network and try again."
        ) from exc

    if response.status_code == 401:
        raise ConsultationAIConfigurationError("Invalid OpenAI API key.")
    if response.status_code == 429:
        raise ConsultationAIRequestError("OpenAI rate limit reached. Wait a moment and try again.")
    if response.status_code >= 400:
        logger.warning(
            "OpenAI API error status=%s body=%s", response.status_code, response.text[:500]
        )
        raise ConsultationAIRequestError("OpenAI could not generate a consultation draft.")

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ConsultationAIResponseError("Unexpected response format from OpenAI.") from exc

    return _parse_model_json(content)
