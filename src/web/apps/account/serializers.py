from apps.applications.models import Application
from apps.projects.models import Project
from apps.projects.serializers import EPPSummarySerializer
from apps.users.serializers import UserProfileSerializer
from rest_framework import serializers


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

    class Meta:
        model = Project
        fields = [
            "pk",
            "title",
            "status",
            "source_type",
            "source_ref",
            "team_size",
            "accepted_participants_count",
            "submitted_applications_count",
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


class CPPRPApplicationsOverviewSerializer(serializers.Serializer):
    totals = serializers.DictField(child=serializers.IntegerField())
    recent = AccountApplicationSerializer(many=True)
