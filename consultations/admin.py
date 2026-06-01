from django.contrib import admin

from consultations.models import Consultation


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "admitted", "discharged", "created_at")
    list_filter = ("admitted", "discharged")
