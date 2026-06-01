"""Honeypot field validation for bot protection."""
from __future__ import annotations

from django import forms


class HoneypotMixin:
    honeypot_field_name = "website"

    def add_honeypot(self) -> None:
        self.fields[self.honeypot_field_name] = forms.CharField(
            required=False,
            widget=forms.TextInput(
                attrs={
                    "tabindex": "-1",
                    "autocomplete": "off",
                    "aria-hidden": "true",
                    "class": "hp-field",
                    "data-lpignore": "true",
                    "data-1p-ignore": "true",
                }
            ),
        )

    def clean_website(self) -> str:
        value = self.cleaned_data.get(self.honeypot_field_name, "")
        if value:
            raise forms.ValidationError("Invalid submission detected.")
        return ""
