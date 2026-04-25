from apps.base.serializers import UserPublicSerializer
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.reverse import reverse

from .initiative_models import InitiativeProposal, InitiativeProposalSubmission
from .serializers import ProjectInlineSerializer


class InitiativeProposalParticipantSerializer(serializers.Serializer):
    full_name = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    study_course = serializers.IntegerField(required=False, allow_null=True)
    education_program = serializers.CharField(required=False, allow_blank=True, default="")
    is_external = serializers.BooleanField(required=False, default=False)


class InitiativeProposalSubmissionSerializer(serializers.ModelSerializer):
    submitted_by = UserPublicSerializer(read_only=True)
    reviewed_by = UserPublicSerializer(read_only=True)
    published_project = ProjectInlineSerializer(read_only=True)

    class Meta:
        model = InitiativeProposalSubmission
        fields = [
            "submission_number",
            "snapshot",
            "submitted_by",
            "submitted_at",
            "decision",
            "comment",
            "reviewed_by",
            "reviewed_at",
            "published_project",
        ]
        read_only_fields = fields


class InitiativeProposalSerializer(serializers.ModelSerializer):
    owner = UserPublicSerializer(read_only=True)
    moderated_by = UserPublicSerializer(read_only=True)
    url = serializers.HyperlinkedIdentityField(
        view_name="api-v1-initiative-proposal-detail",
        lookup_field="pk",
    )
    edit_url = serializers.SerializerMethodField(read_only=True)
    participants = InitiativeProposalParticipantSerializer(many=True, required=False)
    submission_history = InitiativeProposalSubmissionSerializer(
        many=True,
        read_only=True,
        source="submissions",
    )
    published_project = ProjectInlineSerializer(read_only=True)
    tech_tags = serializers.JSONField(required=False, allow_null=True, default=list)

    class Meta:
        model = InitiativeProposal
        fields = [
            "owner",
            "url",
            "edit_url",
            "id",
            "title",
            "description",
            "tech_tags",
            "team_size",
            "study_course",
            "education_program",
            "supervisor_name",
            "supervisor_email",
            "supervisor_department",
            "participants",
            "status",
            "latest_submission_number",
            "moderated_by",
            "moderated_at",
            "moderation_comment",
            "published_project",
            "submission_history",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "latest_submission_number",
            "moderated_by",
            "moderated_at",
            "moderation_comment",
            "published_project",
            "submission_history",
        ]

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_edit_url(self, obj) -> str | None:
        request = self.context.get("request")
        if request is None:
            return None
        return reverse("api-v1-initiative-proposal-detail", kwargs={"pk": obj.pk}, request=request)

    def validate_tech_tags(self, value):
        if value is None:
            return []
        return value

    def validate_participants(self, value):
        if value is None:
            return []
        return value

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance is not None and "status" in attrs and attrs["status"] != instance.status:
            raise serializers.ValidationError(
                {"status": ["Direct status updates are disabled. Use transition action endpoints."]}
            )
        return attrs
