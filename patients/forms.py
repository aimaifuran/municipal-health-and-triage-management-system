"""Patient registration forms for dashboard staff."""

from __future__ import annotations

from django import forms

from patients.models import Gender, Patient


class PatientRegistrationForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = (
            "first_name",
            "middle_name",
            "last_name",
            "birth_date",
            "gender",
            "address",
            "contact_number",
            "emergency_contact",
        )
        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "form-input", "autocomplete": "given-name"}
            ),
            "middle_name": forms.TextInput(
                attrs={"class": "form-input", "autocomplete": "additional-name"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-input", "autocomplete": "family-name"}
            ),
            "birth_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "gender": forms.Select(attrs={"class": "form-input"}),
            "address": forms.Textarea(attrs={"class": "form-input", "rows": 2}),
            "contact_number": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "+639171234567", "autocomplete": "tel"}
            ),
            "emergency_contact": forms.TextInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["middle_name"].required = False
        self.fields["gender"].choices = Gender.choices
