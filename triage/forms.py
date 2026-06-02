"""Forms for nurse triage vitals entry."""

from __future__ import annotations

from decimal import Decimal

from django import forms

from common.validators import (
    validate_blood_pressure,
    validate_body_temperature,
    validate_heart_rate,
    validate_oxygen_saturation,
    validate_respiratory_rate,
)


class TriageVitalsForm(forms.Form):
    blood_pressure = forms.CharField(
        max_length=16,
        label="Blood pressure",
        widget=forms.TextInput(attrs={"placeholder": "120/80", "class": "form-input"}),
    )
    heart_rate = forms.IntegerField(
        label="Heart rate (bpm)",
        min_value=20,
        max_value=300,
        widget=forms.NumberInput(attrs={"placeholder": "72", "class": "form-input"}),
    )
    respiratory_rate = forms.IntegerField(
        label="Respiratory rate",
        min_value=4,
        max_value=60,
        widget=forms.NumberInput(attrs={"placeholder": "16", "class": "form-input"}),
    )
    oxygen_saturation = forms.DecimalField(
        label="SpO₂ (%)",
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("50"),
        max_value=Decimal("100"),
        widget=forms.NumberInput(attrs={"placeholder": "98", "step": "0.1", "class": "form-input"}),
    )
    body_temperature = forms.DecimalField(
        label="Temperature (°C)",
        max_digits=4,
        decimal_places=1,
        min_value=Decimal("32"),
        max_value=Decimal("45"),
        widget=forms.NumberInput(
            attrs={"placeholder": "36.6", "step": "0.1", "class": "form-input"}
        ),
    )
    symptoms = forms.CharField(
        label="Symptoms",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Describe chief complaints and observed symptoms…",
                "class": "form-input",
            }
        ),
    )

    def clean_blood_pressure(self):
        value = self.cleaned_data["blood_pressure"].strip()
        validate_blood_pressure(value)
        return value

    def clean_heart_rate(self):
        value = self.cleaned_data["heart_rate"]
        validate_heart_rate(value)
        return value

    def clean_respiratory_rate(self):
        value = self.cleaned_data["respiratory_rate"]
        validate_respiratory_rate(value)
        return value

    def clean_oxygen_saturation(self):
        value = self.cleaned_data["oxygen_saturation"]
        validate_oxygen_saturation(float(value))
        return value

    def clean_body_temperature(self):
        value = self.cleaned_data["body_temperature"]
        validate_body_temperature(float(value))
        return value

    def clean_symptoms(self):
        value = self.cleaned_data["symptoms"].strip()
        if not value:
            raise forms.ValidationError("Please describe the patient's symptoms.")
        return value
