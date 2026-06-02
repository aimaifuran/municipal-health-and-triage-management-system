from django.urls import path
from rest_framework.routers import DefaultRouter

from api.v1.views import (
    AdmitPatientView,
    BulkDischargeView,
    ConsultationViewSet,
    DischargePatientView,
)

router = DefaultRouter()
router.register("", ConsultationViewSet, basename="consultation")

urlpatterns = [
    path("<uuid:pk>/admit/", AdmitPatientView.as_view(), name="admit"),
    path("<uuid:pk>/discharge/", DischargePatientView.as_view(), name="discharge"),
    path("bulk-discharge/", BulkDischargeView.as_view(), name="bulk-discharge"),
] + router.urls
