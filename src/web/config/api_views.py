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
                "ready": reverse("api-v1-ready", request=request),
                "auth_token": reverse("api-v1-auth-token", request=request),
                "search": reverse("api-v1-search", request=request),
                "recs_search": reverse("api-v1-recs-search", request=request),
                "recs_recommendations": reverse("api-v1-recs-recommendations", request=request),
                "account": reverse("account-me", request=request),
                "imports_epp": reverse("api-v1-import-epp", request=request),
                "outbox_events": reverse("api-v1-outbox-events", request=request),
                "outbox_ack": reverse("api-v1-outbox-events-ack", request=request),
                "outbox_checkpoint_template": (
                    f"{
                    reverse('api-v1-root', request=request)
                    }outbox/consumers/<consumer>/checkpoint/"
                ),
                "projects": reverse("api-v1-project-list", request=request),
                "initiative_proposals": reverse("api-v1-initiative-proposal-list", request=request),
                "applications": reverse("application-list", request=request),
                "users_me": reverse("user-profile-me", request=request),
            }
        )
