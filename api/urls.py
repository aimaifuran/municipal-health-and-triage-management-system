"""API v1 URL routing."""

from django.urls import include, path

urlpatterns = [
    path("auth/", include("api.v1.auth_urls")),
    path("patients/", include("api.v1.patient_urls")),
    path("triage/", include("api.v1.triage_urls")),
    path("consultations/", include("api.v1.consultation_urls")),
    path("analytics/", include("api.v1.analytics_urls")),
    path("public/", include("api.v1.public_urls")),
]
