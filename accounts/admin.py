from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import Clinic, DoctorPatientAssignment, User


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("name", "municipality", "region", "is_active")
    list_filter = ("region", "is_active")
    search_fields = ("name", "municipality")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "role", "clinic", "is_verified", "is_active")
    list_filter = ("role", "clinic", "is_verified")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "role", "clinic", "is_verified")}),
        ("Security", {"fields": ("last_login_ip", "failed_login_attempts")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "role", "clinic")}),
    )


@admin.register(DoctorPatientAssignment)
class DoctorPatientAssignmentAdmin(admin.ModelAdmin):
    list_display = ("doctor", "patient", "is_active")
    list_filter = ("is_active",)
