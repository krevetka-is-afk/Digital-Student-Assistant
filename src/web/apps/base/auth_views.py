from django.conf import settings
from rest_framework import status
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
