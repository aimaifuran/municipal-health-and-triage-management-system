"""JWT serializers using email as username."""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.login_lockout import get_lockout_message, is_login_locked


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        email = (attrs.get("email") or attrs.get("username") or "").strip().lower()
        password = attrs.get("password", "")
        attrs["email"] = email
        attrs["username"] = email

        request = self.context.get("request")
        if request and email and is_login_locked(request, email, password):
            raise serializers.ValidationError(
                {"detail": get_lockout_message()},
                code="locked_out",
            )

        return super().validate(attrs)
