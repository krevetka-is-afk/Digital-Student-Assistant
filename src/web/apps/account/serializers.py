from apps.applications.models import Application
from apps.projects.models import Project
from apps.projects.serializers import EPPSummarySerializer, PrimaryProjectSerializer
from apps.users.serializers import UserProfileSerializer
from rest_framework import serializers

from .models import DocumentTemplate, PlatformDeadline


class PlatformDeadlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformDeadline
        fields = [
            "id",
            "slug",
            "title",
            "audience",
            "description",
            "starts_at",
            "ends_at",
            "is_active",
            "created_at",
            "updated_at",
        ]


class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = [
            "id",
            "slug",
            "title",
            "audience",
            "url",
            "description",
            "is_active",
            "metadata",
            "created_at",
            "updated_at",
        ]


class AccountProjectSerializer(serializers.ModelSerializer):
    epp = EPPSummarySerializer(read_only=True)
    epp_id = serializers.IntegerField(read_only=True)
    epp_title = serializers.CharField(source="epp.title", read_only=True, allow_null=True)
    campaign_title = serializers.CharField(
        source="epp.campaign_title",
        read_only=True,
        allow_null=True,
    )
    source_status_raw = serializers.CharField(source="status_raw", read_only=True)
    submitted_applications_count = serializers.SerializerMethodField()
    staffing_state = serializers.CharField(read_only=True)
    application_window_state = serializers.CharField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "pk",
            "title",
            "status",
            "source_type",
            "source_ref",
            "team_size",
            "study_course",
            "education_program",
            "accepted_participants_count",
            "submitted_applications_count",
            "staffing_state",
            "application_window_state",
            "application_opened_at",
            "application_deadline",
            "epp",
            "epp_id",
            "epp_title",
            "campaign_title",
            "source_status_raw",
            "created_at",
            "updated_at",
        ]

    def get_submitted_applications_count(self, obj) -> int:
        return int(getattr(obj, "submitted_applications_count", 0) or 0)


class AccountApplicationSerializer(serializers.ModelSerializer):
    project = AccountProjectSerializer(read_only=True)
    applicant_username = serializers.CharField(source="applicant.username", read_only=True)
    applicant_email = serializers.EmailField(source="applicant.email", read_only=True)

    class Meta:
        model = Application
        fields = [
            "id",
            "status",
            "motivation",
            "review_comment",
            "created_at",
            "updated_at",
            "applicant_username",
            "applicant_email",
            "project",
        ]


class AccountOverviewSerializer(serializers.Serializer):
    profile = UserProfileSerializer()
    counters = serializers.DictField(child=serializers.IntegerField())


class StudentOverviewSerializer(AccountOverviewSerializer):
    applications = AccountApplicationSerializer(many=True)
    favorite_projects = PrimaryProjectSerializer(many=True)
    deadlines = PlatformDeadlineSerializer(many=True)
    templates = DocumentTemplateSerializer(many=True)


class PaginatedAccountApplicationSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = AccountApplicationSerializer(many=True)


class CPPRPApplicationsOverviewSerializer(serializers.Serializer):
    totals = serializers.DictField(child=serializers.IntegerField())
    recent = PaginatedAccountApplicationSerializer()
