from rest_framework.routers import DefaultRouter

from api.v1.views import TriageViewSet

router = DefaultRouter()
router.register("", TriageViewSet, basename="triage")

urlpatterns = router.urls
