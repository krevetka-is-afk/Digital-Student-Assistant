from apps.projects.models import Project
from apps.projects.serializers import PrimaryProjectSerializer
from rest_framework import serializers

from .models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    email_verified = serializers.BooleanField(read_only=True)
    favorite_projects_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "username",
            "email",
            "role",
            "interests",
            "favorite_project_ids",
            "email_verified",
            "email_verified_at",
            "favorite_projects_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "email_verified",
            "email_verified_at",
            "created_at",
            "updated_at",
        ]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request is None or not getattr(request.user, "is_staff", False):
            fields["role"].read_only = True
        return fields

    def validate(self, attrs):
        request = self.context.get("request")
        if "role" in getattr(self, "initial_data", {}) and (
            request is None or not getattr(request.user, "is_staff", False)
        ):
            raise serializers.ValidationError(
                {"role": ["You cannot change role via this endpoint."]}
            )
        return super().validate(attrs)

    def get_favorite_projects_count(self, obj) -> int:
        return len(obj.favorite_project_ids or [])


class FavoriteProjectsUpdateSerializer(serializers.Serializer):
    project_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )
    project_id = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        project_ids = list(attrs.get("project_ids") or [])
        project_id = attrs.get("project_id")
        if project_id is not None:
            project_ids.append(project_id)
        if project_ids:
            unique_ids = list(dict.fromkeys(project_ids))
            if Project.objects.filter(pk__in=unique_ids).count() != len(unique_ids):
                raise serializers.ValidationError({"project_ids": ["Some projects do not exist."]})
            attrs["project_ids"] = unique_ids
        return attrs


class FavoriteProjectsResponseSerializer(serializers.Serializer):
    project_ids = serializers.ListField(child=serializers.IntegerField())
    items = PrimaryProjectSerializer(many=True)
