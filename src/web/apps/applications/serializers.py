from rest_framework import serializers

from .models import Application


class ProjectInlineSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    tech_tags = serializers.JSONField(read_only=True)
    status = serializers.CharField(read_only=True)
    team_size = serializers.IntegerField(read_only=True)
    accepted_participants_count = serializers.IntegerField(read_only=True)


class ApplicantInlineSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk", read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    full_name = serializers.SerializerMethodField(read_only=True)

    def get_full_name(self, obj):
        return obj.get_full_name()


class ApplicationSerializer(serializers.ModelSerializer):
    project_detail = ProjectInlineSerializer(source="project", read_only=True)
    applicant_detail = ApplicantInlineSerializer(source="applicant", read_only=True)

    class Meta:
        model = Application
        fields = [
            "id",
            "project",
            "project_detail",
            "applicant",
            "applicant_detail",
            "status",
            "motivation",
            "review_comment",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "applicant",
            "review_comment",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance is not None and "status" in attrs and attrs["status"] != instance.status:
            raise serializers.ValidationError(
                {"status": ["Direct status updates are disabled. Use transition action endpoints."]}
            )
        return attrs
