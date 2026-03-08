from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView


class ApiRootView(APIView):
    permission_classes = [AllowAny]
    name = "API Root"

    def get(self, request, *args, **kwargs):
        return Response(
            {
                "default_version": "v1",
                "versions": {
                    "v1": reverse("api-v1-root", request=request),
                },
                "schema": reverse("api-schema", request=request),
                "docs": reverse("api-docs", request=request),
                "legacy": {
                    "deprecated": True,
                    "root": reverse("legacy-api-root", request=request),
                    "add": reverse("legacy-api-add", request=request),
                },
            }
        )


class ApiV1RootView(APIView):
    permission_classes = [AllowAny]
    name = "API v1 Root"

    def get(self, request, *args, **kwargs):
        return Response(
            {
                "version": "v1",
                "health": reverse("api-v1-health", request=request),
                "auth_token": reverse("api-v1-auth-token", request=request),
                "search": reverse("api-v1-search", request=request),
                "projects": reverse("api-v1-project-list", request=request),
                "applications": reverse("application-list", request=request),
                "users_me": reverse("user-profile-me", request=request),
            }
        )
