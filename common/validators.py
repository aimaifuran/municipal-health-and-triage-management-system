"""Shared validators for medical and contact data."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

phone_validator = RegexValidator(
    regex=r"^\+?[\d\s\-()]{7,20}$",
    message="Enter a valid phone number (7-20 digits).",
)

blood_pressure_pattern = re.compile(r"^\d{2,3}/\d{2,3}$")


def validate_blood_pressure(value: str) -> None:
    if not blood_pressure_pattern.match(value):
        raise ValidationError("Blood pressure must be in format systolic/diastolic (e.g. 120/80).")


def validate_heart_rate(value: int) -> None:
    if not 20 <= value <= 300:
        raise ValidationError("Heart rate must be between 20 and 300 bpm.")


def validate_respiratory_rate(value: int) -> None:
    if not 4 <= value <= 60:
        raise ValidationError("Respiratory rate must be between 4 and 60.")


def validate_oxygen_saturation(value: float) -> None:
    if not 50.0 <= value <= 100.0:
        raise ValidationError("Oxygen saturation must be between 50% and 100%.")


def validate_body_temperature(value: float) -> None:
    if not 32.0 <= value <= 45.0:
        raise ValidationError("Body temperature must be between 32°C and 45°C.")
