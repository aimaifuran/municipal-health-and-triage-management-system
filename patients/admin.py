from django.contrib import admin

from patients.models import Patient, PatientDocument


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("patient_number", "full_name", "clinic", "birth_date", "archived_at")
    list_filter = ("clinic", "gender")
    search_fields = ("patient_number", "first_name", "last_name")
    readonly_fields = ("patient_number",)


@admin.register(PatientDocument)
class PatientDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "patient", "uploaded_by", "created_at")
