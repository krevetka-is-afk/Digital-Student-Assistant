from apps.base.serializers import UserPublicSerializer
from rest_framework import serializers
from rest_framework.reverse import reverse

from . import validators
from .models import EPP, Project


class ProjectInlineSerializer(serializers.Serializer):
    url = serializers.HyperlinkedIdentityField(view_name="api-v1-project-detail", lookup_field="pk")
    title = serializers.CharField(read_only=True)


class EPPSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = EPP
        fields = ["id", "source_ref", "title", "campaign_title", "status_raw"]


class PrimaryProjectSerializer(serializers.ModelSerializer):
    owner = UserPublicSerializer(read_only=True)
    moderated_by = UserPublicSerializer(read_only=True)
    edit_url = serializers.SerializerMethodField(read_only=True)
    url = serializers.HyperlinkedIdentityField(view_name="api-v1-project-detail", lookup_field="pk")
    epp = EPPSummarySerializer(read_only=True)
    extra_data = serializers.JSONField(required=False, allow_null=True, default=dict)
    raw_payload = serializers.JSONField(required=False, allow_null=True, default=dict)
    tech_tags = serializers.JSONField(required=False, allow_null=True, default=list)
    source_ref = serializers.CharField(required=False, allow_blank=True, default="")

    title = serializers.CharField(validators=[validators.validate_title_no_hello])

    class Meta:
        model = Project
        fields = [
            "epp",
            "owner",
            "url",
            "edit_url",
            "pk",
            "title",
            "description",
            "tech_tags",
            "status",
            "status_raw",
            "team_size",
            "accepted_participants_count",
            "source_type",
            "source_ref",
            "source_row_index",
            "vacancy_title",
            "vacancy_title_en",
            "thesis_title",
            "thesis_title_en",
            "supervisor_name",
            "supervisor_email",
            "extra_data",
            "raw_payload",
            "moderated_by",
            "moderated_at",
            "moderation_comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "accepted_participants_count",
            "moderated_by",
            "moderated_at",
            "source_row_index",
        ]

    def get_edit_url(self, obj):
        request = self.context.get("request")
        if request is None:
            return None
        return reverse("api-v1-project-detail", kwargs={"pk": obj.pk}, request=request)

    def validate_extra_data(self, value):
        if value is None:
            return {}
        return value

    def validate_raw_payload(self, value):
        if value is None:
            return {}
        return value

    def validate_tech_tags(self, value):
        if value is None:
            return []
        return value

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance is not None and "status" in attrs and attrs["status"] != instance.status:
            raise serializers.ValidationError(
                {"status": ["Direct status updates are disabled. Use transition action endpoints."]}
            )
        if "vacancy_title" in attrs and not attrs.get("title"):
            attrs["title"] = attrs["vacancy_title"]
        if "title" in attrs and not attrs.get("vacancy_title"):
            attrs["vacancy_title"] = attrs["title"]
        return attrs


class SecondaryProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["title", "description", "status", "created_at"]
