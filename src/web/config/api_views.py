from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView


class ApiRootVersionsSerializer(serializers.Serializer):
    v1 = serializers.URLField()


class ApiRootResponseSerializer(serializers.Serializer):
    default_version = serializers.CharField()
    versions = ApiRootVersionsSerializer()
    schema = serializers.URLField()
    docs = serializers.URLField()


class ApiV1RootResponseSerializer(serializers.Serializer):
    version = serializers.CharField()
    health = serializers.URLField()
    ready = serializers.URLField()
    auth_token = serializers.URLField()
    search = serializers.URLField()
    recs_search = serializers.URLField()
    recs_recommendations = serializers.URLField()
    account = serializers.URLField()
    imports_epp = serializers.URLField()
    outbox_events = serializers.URLField()
    outbox_ack = serializers.URLField()
    outbox_checkpoint_template = serializers.CharField()
    projects = serializers.URLField()
    initiative_proposals = serializers.URLField()
    applications = serializers.URLField()
    users_me = serializers.URLField()


class ApiRootView(APIView):
    permission_classes = [AllowAny]
    name = "API Root"

    @extend_schema(responses=ApiRootResponseSerializer)
    def get(self, request, *args, **kwargs):
        return Response(
            {
                "default_version": "v1",
                "versions": {
                    "v1": reverse("api-v1-root", request=request),
                },
                "schema": reverse("api-schema", request=request),
                "docs": reverse("api-docs", request=request),
            }
        )


class ApiV1RootView(APIView):
    permission_classes = [AllowAny]
    name = "API v1 Root"

    @extend_schema(responses=ApiV1RootResponseSerializer)
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
