from django.contrib import admin

from auditlogs.models import AuditLog, LoginAttempt


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "object_type", "user", "ip_address", "timestamp")
    list_filter = ("action", "object_type")
    readonly_fields = ("timestamp",)


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("email_attempted", "success", "ip_address", "timestamp")
    list_filter = ("success",)
