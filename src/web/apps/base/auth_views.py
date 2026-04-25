from typing import Any, cast

from apps.users.email_verification import pending_email_verification_user_for_credentials
from django.conf import settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.response import Response


class ProviderAwareObtainAuthTokenView(ObtainAuthToken):
    """
    Keep local token issuance available only when local fallback is enabled.
    """

    def post(self, request, *args, **kwargs):
        if not getattr(settings, "AUTH_ENABLE_LOCAL_TOKEN_FALLBACK", True):
            return Response(
                {"detail": "Local token auth is disabled in current auth mode."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return super().post(request, *args, **kwargs)


class VerifiedObtainAuthTokenView(ProviderAwareObtainAuthTokenView):
    def post(self, request, *args, **kwargs):
        if not getattr(settings, "AUTH_ENABLE_LOCAL_TOKEN_FALLBACK", True):
            return Response(
                {"detail": "Local token auth is disabled in current auth mode."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.serializer_class(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            token_model = cast(Any, Token)
            token, _ = token_model.objects.get_or_create(user=user)
            return Response({"token": token.key})

        identifier = request.data.get("username") or request.data.get("email") or ""
        password = request.data.get("password") or ""
        pending_user = pending_email_verification_user_for_credentials(identifier, password)
        if pending_user is not None:
            return Response(
                {
                    "detail": "Email verification is required before requesting an auth token.",
                    "code": "email_not_verified",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
