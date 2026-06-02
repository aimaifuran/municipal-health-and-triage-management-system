"""Forms for doctor consultation entry from the active queue."""

from __future__ import annotations

from django import forms

from consultations.models import Consultation


class ConsultationRecordForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = ("diagnosis", "treatment", "prescription", "consultation_notes")
        widgets = {
            "diagnosis": forms.Textarea(
                attrs={"class": "form-input", "rows": 3, "placeholder": "Primary diagnosis"}
            ),
            "treatment": forms.Textarea(
                attrs={"class": "form-input", "rows": 3, "placeholder": "Treatment plan"}
            ),
            "prescription": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 2,
                    "placeholder": "Optional — medications and dosage",
                }
            ),
            "consultation_notes": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 2,
                    "placeholder": "Optional — follow-up or clinical notes",
                }
            ),
        }
