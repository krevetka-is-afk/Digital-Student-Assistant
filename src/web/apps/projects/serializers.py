from apps.base.serializers import UserPublicSerializer
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.reverse import reverse

from . import validators
from .models import EPP, Project, Technology
from .normalization import normalize_technology_tags


class ProjectInlineSerializer(serializers.Serializer):
    url = serializers.HyperlinkedIdentityField(view_name="api-v1-project-detail", lookup_field="pk")
    title = serializers.CharField(read_only=True)


class EPPSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = EPP
        fields = ["id", "source_ref", "title", "campaign_title", "status_raw"]


class TechnologySerializer(serializers.ModelSerializer):
    class Meta:
        model = Technology
        fields = ["id", "name", "normalized_name", "status"]
        read_only_fields = fields


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
    applications_count = serializers.SerializerMethodField(read_only=True)
    staffing_state = serializers.CharField(read_only=True)
    application_window_state = serializers.CharField(read_only=True)
    is_team_project = serializers.BooleanField(read_only=True)
    is_favorite = serializers.SerializerMethodField(read_only=True)

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
            "study_course",
            "education_program",
            "accepted_participants_count",
            "applications_count",
            "staffing_state",
            "application_window_state",
            "is_team_project",
            "is_favorite",
            "source_type",
            "source_ref",
            "source_row_index",
            "vacancy_title",
            "vacancy_title_en",
            "thesis_title",
            "thesis_title_en",
            "implementation_language",
            "activity_type",
            "supervisor_name",
            "supervisor_email",
            "supervisor_department",
            "control_form",
            "work_format",
            "application_opened_at",
            "application_deadline",
            "student_participation_format",
            "results_presentation_format",
            "grading_formula",
            "implementation_features",
            "selection_criteria",
            "is_paid",
            "retakes_allowed",
            "location",
            "internal_customer",
            "external_customer_location",
            "external_customer",
            "organization_type",
            "cooperation_type",
            "uses_ai",
            "digital_tools",
            "usage_areas",
            "python_libraries",
            "methods",
            "programming_languages",
            "data_tools",
            "vacancy_initiator",
            "vacancy_initiator_type",
            "vacancy_tags",
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

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_edit_url(self, obj) -> str | None:
        request = self.context.get("request")
        if request is None:
            return None
        return reverse("api-v1-project-detail", kwargs={"pk": obj.pk}, request=request)

    def get_applications_count(self, obj) -> int:
        if hasattr(obj, "applications_count"):
            return int(getattr(obj, "applications_count") or 0)
        return obj.applications.count()

    def get_is_favorite(self, obj) -> bool:
        request = self.context.get("request")
        if request is None or not getattr(request.user, "is_authenticated", False):
            return False
        profile = getattr(request.user, "profile", None)
        if profile is None:
            return False
        return obj.pk in (profile.favorite_project_ids or [])

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
        if not isinstance(value, list):
            raise serializers.ValidationError("Expected a list of technology tags.")
        return normalize_technology_tags(value)

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
