from rest_framework_simplejwt.views import TokenObtainPairView

from api.v1.auth_serializers import EmailTokenObtainPairSerializer
from auditlogs.services import AuditService


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        email = request.data.get("email") or request.data.get("username", "")
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            AuditService.log_login_attempt(email, True, request)
        else:
            AuditService.log_login_attempt(email, False, request)
        return response
