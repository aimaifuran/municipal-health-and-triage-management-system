from django.urls import path

from api.v1.views import ClinicStatisticsView, RegionalStatisticsView

urlpatterns = [
    path("clinic/", ClinicStatisticsView.as_view(), name="clinic-stats"),
    path("regional/", RegionalStatisticsView.as_view(), name="regional-stats"),
    path("severity/", ClinicStatisticsView.as_view(), name="severity-distribution"),
    path("trends/", ClinicStatisticsView.as_view(), name="patient-trends"),
]
