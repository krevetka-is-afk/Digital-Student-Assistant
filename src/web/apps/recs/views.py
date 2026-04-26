import logging

from apps.users.models import UserProfile
from apps.users.utils import user_is_moderator
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class IsCpprpOrStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or user_is_moderator(request.user))
        )


from .serializers import (  # noqa: E402
    RecommendationReindexRequestSerializer,
    RecommendationReindexResponseSerializer,
    RecommendationRequestSerializer,
    RecommendationResponseSerializer,
    SearchRequestSerializer,
)
from .services import recommend_projects, search_projects  # noqa: E402


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
        reason = request.data.get("reason", "manual_reindex")
        logger.info(
            "recs.reindex_requested user=%s reason=%s",
            request.user.id,
            reason,
        )
        return Response({"status": "accepted"})
