"""JWT serializers using email as username."""
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        attrs["username"] = attrs.get("email", attrs.get("username", ""))
        return super().validate(attrs)
