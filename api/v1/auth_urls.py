from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from api.v1.auth_views import EmailTokenObtainPairView
from api.v1.views import LogoutView, ProfileView

urlpatterns = [
    path("login/", EmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="token_logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
]
