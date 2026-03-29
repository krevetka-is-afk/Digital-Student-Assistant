from apps.account.permissions import IsCpprpOrStaff
from apps.outbox.services import emit_event
from apps.users.models import UserProfile
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    RecommendationReindexRequestSerializer,
    RecommendationReindexResponseSerializer,
    RecommendationRequestSerializer,
    RecommendationResponseSerializer,
    SearchRequestSerializer,
)
from .services import recommend_projects, search_projects


def _serialize_items(items, request):
    from apps.projects.serializers import PrimaryProjectSerializer

    return [
        {
            "project": PrimaryProjectSerializer(item["project"], context={"request": request}).data,
            "score": item["score"],
            "reason": item["reason"],
        }
        for item in items
    ]


class SearchProxyAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        parameters=[SearchRequestSerializer],
        responses=RecommendationResponseSerializer,
    )
    def get(self, request):
        serializer = SearchRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        mode, items = search_projects(
            serializer.validated_data["q"],
            limit=serializer.validated_data["limit"],
        )
        payload = {"items": _serialize_items(items, request), "mode": mode}
        return Response(payload)


class RecommendationListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[RecommendationRequestSerializer],
        responses=RecommendationResponseSerializer,
    )
    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = RecommendationRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        interests = serializer.validated_data["interests"] or profile.interests
        mode, items = recommend_projects(interests, limit=serializer.validated_data["limit"])
        payload = {"items": _serialize_items(items, request), "mode": mode}
        return Response(payload)


class RecommendationReindexAPIView(APIView):
    permission_classes = [IsCpprpOrStaff]

    @extend_schema(
        request=RecommendationReindexRequestSerializer,
        responses=RecommendationReindexResponseSerializer,
    )
    def post(self, request):
        emit_event(
            event_type="recs.reindex_requested",
            aggregate_type="recs",
            aggregate_id="global",
            payload={
                "requested_by_id": request.user.id,
                "reason": request.data.get("reason", "manual_reindex"),
            },
            idempotency_key=(
                f"recs.reindex_requested:{request.user.id}:"
                f"{request.data.get('reason', 'manual_reindex')}"
            ),
        )
        return Response({"status": "accepted"})
