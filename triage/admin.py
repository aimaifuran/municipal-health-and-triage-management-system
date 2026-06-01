from django.contrib import admin

from triage.models import TriageRecord


@admin.register(TriageRecord)
class TriageRecordAdmin(admin.ModelAdmin):
    list_display = ("patient", "severity_level", "priority_score", "triage_status", "is_active")
    list_filter = ("severity_level", "triage_status", "is_active")
