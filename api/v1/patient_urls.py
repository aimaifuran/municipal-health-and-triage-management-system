from django.urls import path
from rest_framework.routers import DefaultRouter

from api.v1.views import PatientQueueView, PatientViewSet

router = DefaultRouter()
router.register("", PatientViewSet, basename="patient")

urlpatterns = [
    path("queue/", PatientQueueView.as_view(), name="patient-queue"),
] + router.urls
