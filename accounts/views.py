"""Authentication views."""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from accounts.forms import LoginForm
from auditlogs.services import AuditService


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = LoginForm()
        return context

    def form_valid(self, form):
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
            AuditService.log_login_attempt(email, False, self.request)

        if form.non_field_errors():
            for error in form.non_field_errors():
                messages.error(self.request, error)
        else:
            for field in form.visible_fields():
                for error in field.errors:
                    messages.error(self.request, error)
            if not any(form.errors):
                messages.error(
                    self.request,
                    "Invalid email or password. Please check your credentials and try again.",
                )

        return redirect("accounts:login")

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
