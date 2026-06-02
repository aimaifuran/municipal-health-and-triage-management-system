"""Account forms with honeypot protection."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm

from accounts.models import Clinic, UserRole
from accounts.profile_storage import validate_profile_image
from accounts.services import STAFF_ROLES
from security.honeypot import HoneypotMixin

User = get_user_model()

INPUT = {"class": "form-input"}


class ClinicForm(forms.ModelForm):
    class Meta:
        model = Clinic
        fields = ("name", "address", "municipality", "region", "is_active")
        widgets = {
            "name": forms.TextInput(attrs=INPUT),
            "address": forms.Textarea(attrs={**INPUT, "rows": 2}),
            "municipality": forms.TextInput(attrs=INPUT),
            "region": forms.TextInput(attrs=INPUT),
            "is_active": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-teal-600"}
            ),
        }


class StaffUserForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={**INPUT, "autocomplete": "email", "placeholder": "nurse@mhtms.gov.ph"}
        ),
    )
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs=INPUT))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs=INPUT))
    role = forms.ChoiceField(
        choices=[(r, label) for r, label in UserRole.choices if r in STAFF_ROLES],
        widget=forms.Select(attrs=INPUT),
    )
    clinic = forms.ModelChoiceField(
        queryset=Clinic.objects.order_by("name"),
        widget=forms.Select(attrs=INPUT),
    )
    password = forms.CharField(
        required=False,
        min_length=8,
        widget=forms.PasswordInput(
            attrs={**INPUT, "autocomplete": "new-password", "placeholder": "Min. 8 characters"},
        ),
        help_text="Leave blank when editing to keep the current password.",
    )
    is_active = forms.BooleanField(required=False, initial=True)
    is_verified = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, instance: User | None = None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        self.fields["clinic"].queryset = Clinic.objects.order_by("name")
        if instance:
            self.fields["email"].disabled = True
            self.fields["email"].initial = instance.email
            self.fields["first_name"].initial = instance.first_name
            self.fields["last_name"].initial = instance.last_name
            self.fields["role"].initial = instance.role
            self.fields["clinic"].initial = instance.clinic_id
            self.fields["is_active"].initial = instance.is_active
            self.fields["is_verified"].initial = instance.is_verified
            self.fields["password"].required = False
        else:
            self.fields["password"].required = True
            self.fields["is_active"].initial = True
            self.fields["is_verified"].initial = True

    def clean_email(self):
        if self.instance:
            return self.instance.email
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")
        qs = User.objects.filter(email__iexact=email)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        if not self.instance and not cleaned.get("password"):
            self.add_error("password", "Password is required for new staff accounts.")
        return cleaned


class LoginForm(HoneypotMixin, AuthenticationForm):
    """Email-based login; relies on AuthenticationForm.authenticate(request=...)."""

    error_messages = {
        "invalid_login": "Invalid credentials",
        "inactive": "This account has been deactivated.",
    }

    username = forms.EmailField(
        label="Email",
        error_messages={
            "required": "Email is required.",
            "invalid": "Enter a valid email address.",
        },
        widget=forms.EmailInput(
            attrs={
                "class": "form-input login-email-input",
                "placeholder": "doctor@mhtms.gov.ph",
                "autocomplete": "username",
                "spellcheck": "false",
                "inputmode": "email",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        error_messages={"required": "Password is required."},
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "••••••••",
                "autocomplete": "current-password",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.setdefault("name", "username")
        self.add_honeypot()


class ProfileDetailsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            "first_name": forms.TextInput(attrs={**INPUT, "autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={**INPUT, "autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={**INPUT, "autocomplete": "email"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


class ProfilePasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("old_password", "new_password1", "new_password2"):
            self.fields[name].widget.attrs["class"] = "form-input"


class ProfilePictureForm(forms.Form):
    picture = forms.ImageField(
        required=True,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "block w-full text-sm text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-teal-50 file:text-teal-700 hover:file:bg-teal-100",
                "accept": "image/jpeg,image/png,image/webp",
            }
        ),
    )

    def clean_picture(self):
        picture = self.cleaned_data["picture"]
        validate_profile_image(picture)
        return picture
