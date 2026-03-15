from apps.base.serializers import UserPublicSerializer
from rest_framework import serializers
from rest_framework.reverse import reverse

from . import validators
from .models import Project


class ProjectInlineSerializer(serializers.Serializer):
    url = serializers.HyperlinkedIdentityField(view_name="api-v1-project-detail", lookup_field="pk")
    title = serializers.CharField(read_only=True)


class PrimaryProjectSerializer(serializers.ModelSerializer):
    owner = UserPublicSerializer(read_only=True)
    moderated_by = UserPublicSerializer(read_only=True)
    edit_url = serializers.SerializerMethodField(read_only=True)
    url = serializers.HyperlinkedIdentityField(view_name="api-v1-project-detail", lookup_field="pk")
    extra_data = serializers.JSONField(required=False, allow_null=True, default=dict)
    tech_tags = serializers.JSONField(required=False, allow_null=True, default=dict)

    title = serializers.CharField(
        validators=[validators.unique_project_title, validators.validate_title_no_hello]
    )

    class Meta:
        model = Project
        fields = [
            "owner",
            "url",
            "edit_url",
            "pk",
            "title",
            "description",
            "tech_tags",
            "status",
            "team_size",
            "accepted_participants_count",
            "source_type",
            "source_ref",
            "extra_data",
            "moderated_by",
            "moderated_at",
            "moderation_comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["accepted_participants_count", "moderated_by", "moderated_at"]

    def get_edit_url(self, obj):
        request = self.context.get("request")
        if request is None:
            return None
        return reverse("api-v1-project-detail", kwargs={"pk": obj.pk}, request=request)

    def validate_extra_data(self, value):
        if value is None:
            return {}
        return value

    def validate_tech_tags(self, value):
        if value is None:
            return {}
        return value

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance is not None and "status" in attrs and attrs["status"] != instance.status:
            raise serializers.ValidationError(
                {"status": ["Direct status updates are disabled. Use transition action endpoints."]}
            )
        return attrs


class SecondaryProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["title", "description", "status", "created_at"]
