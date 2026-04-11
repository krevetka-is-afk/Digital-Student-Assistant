from apps.outbox.services import emit_event
from apps.projects.models import Project, ProjectStatus
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserProfile
from .serializers import (
    FavoriteProjectsResponseSerializer,
    FavoriteProjectsUpdateSerializer,
    UserProfileSerializer,
)


class MyProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=UserProfileSerializer)
    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return Response(UserProfileSerializer(profile).data)

    @extend_schema(request=UserProfileSerializer, responses=UserProfileSerializer)
    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(
            profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        emit_event(
            event_type="user_profile.changed",
            aggregate_type="user_profile",
            aggregate_id=profile.pk,
            payload=UserProfileSerializer(profile).data,
            idempotency_key=f"user_profile.changed:{profile.pk}:{profile.updated_at.isoformat()}",
        )
        return Response(serializer.data)

    @extend_schema(request=UserProfileSerializer, responses=UserProfileSerializer)
    def put(self, request):
        return self.patch(request)


class MyFavoriteProjectsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=FavoriteProjectsResponseSerializer)
    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        projects = list(
            Project.objects.filter(
                pk__in=profile.favorite_project_ids or [],
                status__in=ProjectStatus.catalog_values(),
            ).select_related("owner", "epp")
        )
        payload = {"project_ids": list(profile.favorite_project_ids or []), "items": projects}
        return Response(
            FavoriteProjectsResponseSerializer(payload, context={"request": request}).data
        )

    @extend_schema(
        request=FavoriteProjectsUpdateSerializer,
        responses=FavoriteProjectsResponseSerializer,
    )
    def put(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = FavoriteProjectsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile.set_favorite_project_ids(serializer.validated_data.get("project_ids", []))
        profile.save(update_fields=["favorite_project_ids", "updated_at"])
        emit_event(
            event_type="user_profile.changed",
            aggregate_type="user_profile",
            aggregate_id=profile.pk,
            payload=UserProfileSerializer(profile).data,
            idempotency_key=f"user_profile.changed:{profile.pk}:{profile.updated_at.isoformat()}",
        )
        return self.get(request)

    @extend_schema(
        request=FavoriteProjectsUpdateSerializer,
        responses=FavoriteProjectsResponseSerializer,
    )
    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = FavoriteProjectsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project_ids = list(profile.favorite_project_ids or [])
        project_ids.extend(serializer.validated_data.get("project_ids", []))
        profile.set_favorite_project_ids(project_ids)
        profile.save(update_fields=["favorite_project_ids", "updated_at"])
        emit_event(
            event_type="user_profile.changed",
            aggregate_type="user_profile",
            aggregate_id=profile.pk,
            payload=UserProfileSerializer(profile).data,
            idempotency_key=f"user_profile.changed:{profile.pk}:{profile.updated_at.isoformat()}",
        )
        return self.get(request)


class MyFavoriteProjectDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={204: None})
    def delete(self, request, pk: int):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        project_ids = [
            project_id for project_id in profile.favorite_project_ids or [] if project_id != pk
        ]
        profile.set_favorite_project_ids(project_ids)
        profile.save(update_fields=["favorite_project_ids", "updated_at"])
        emit_event(
            event_type="user_profile.changed",
            aggregate_type="user_profile",
            aggregate_id=profile.pk,
            payload=UserProfileSerializer(profile).data,
            idempotency_key=f"user_profile.changed:{profile.pk}:{profile.updated_at.isoformat()}",
        )
        return Response(status=204)
