"""Authentication and profile views."""

import logging

from axes.helpers import get_lockout_message
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from accounts.forms import LoginForm, ProfileDetailsForm, ProfilePasswordForm, ProfilePictureForm
from accounts.login_lockout import is_login_locked, record_failed_login
from accounts.profile_service import ProfileService
from auditlogs.models import AuditAction
from auditlogs.services import AuditService

logger = logging.getLogger(__name__)


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def get(self, request, *args, **kwargs):
        """Always show a fresh form on GET (errors come from flash messages only)."""
        response = super().get(request, *args, **kwargs)
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        return response

    def form_valid(self, form):
        username = form.cleaned_data.get("username", "")
        password = form.cleaned_data.get("password", "")
        if is_login_locked(self.request, username, password):
            self.request.axes_locked_out = False
            form.add_error(None, get_lockout_message())
            AuditService.log_login_attempt(username, False, self.request)
            return self.form_invalid(form)

        user = form.get_user()
        ip = self.request.META.get("REMOTE_ADDR")
        user.last_login_ip = ip
        user.reset_failed_login()
        user.save(update_fields=["last_login_ip", "failed_login_attempts"])
        AuditService.log_login_attempt(user.email, True, self.request)
        login(self.request, user)
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        email = self.request.POST.get("username", "")
        if email:
            record_failed_login(email)
            AuditService.log_login_attempt(email, False, self.request)
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse_lazy("dashboard:home")


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            from auditlogs.models import AuditAction
            from auditlogs.services import AuditService

            AuditService.log(
                action=AuditAction.LOGOUT,
                object_type="User",
                object_id=str(request.user.id),
                user=request.user,
                request=request,
            )
        return super().dispatch(request, *args, **kwargs)


class ProfileView(LoginRequiredMixin, TemplateView):
    """Manage profile details, password, and profile picture."""

    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(
            {
                "details_form": ProfileDetailsForm(instance=user),
                "password_form": ProfilePasswordForm(user=user),
                "picture_form": ProfilePictureForm(),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")
        user = request.user

        if action == "details":
            return self._post_details(request, user)
        if action == "password":
            return self._post_password(request, user)
        if action == "picture":
            return self._post_picture(request, user)
        if action == "remove_picture":
            return self._post_remove_picture(request, user)

        messages.error(request, "Unknown profile action.")
        return redirect("accounts:profile")

    def _post_details(self, request, user):
        form = ProfileDetailsForm(request.POST, instance=user)
        if form.is_valid():
            ProfileService.update_details(
                user=user,
                validated_data=form.cleaned_data,
                request=request,
            )
            messages.success(request, "Profile details updated.")
        else:
            for error in form.errors.values():
                messages.error(request, error[0])
        return redirect("accounts:profile")

    def _post_password(self, request, user):
        form = ProfilePasswordForm(user=user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, user)
            AuditService.log(
                action=AuditAction.UPDATE,
                object_type="User",
                object_id=str(user.pk),
                user=user,
                request=request,
                details={"section": "password_change"},
            )
            messages.success(request, "Password changed successfully.")
        else:
            for error in form.errors.values():
                messages.error(request, error[0])
        return redirect("accounts:profile")

    def _post_picture(self, request, user):
        form = ProfilePictureForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                ProfileService.update_picture(
                    user=user,
                    uploaded_file=form.cleaned_data["picture"],
                    request=request,
                )
                messages.success(request, "Profile picture updated.")
            except ValidationError as exc:
                messages.error(request, exc.messages[0] if exc.messages else str(exc))
            except Exception as exc:
                logger.exception("Profile picture upload failed for user %s", user.pk)
                if settings.DEBUG:
                    messages.error(request, f"Could not upload profile picture: {exc}")
                else:
                    messages.error(
                        request,
                        "Could not upload profile picture. Check Cloudinary settings and try again.",
                    )
        else:
            for error in form.errors.values():
                messages.error(request, error[0])
        return redirect("accounts:profile")

    def _post_remove_picture(self, request, user):
        ProfileService.remove_picture(user=user, request=request)
        messages.success(request, "Profile picture removed.")
        return redirect("accounts:profile")
