from django.urls import path

from api.v1.views import PublicMaskedStatsView

urlpatterns = [
    path("health-stats/", PublicMaskedStatsView.as_view(), name="public-health-stats"),
]
