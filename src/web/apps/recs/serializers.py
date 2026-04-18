from apps.projects.serializers import PrimaryProjectSerializer
from rest_framework import serializers


class RecommendationRequestSerializer(serializers.Serializer):
    interests = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        default=list,
    )
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=10)


class SearchRequestSerializer(serializers.Serializer):
    q = serializers.CharField(required=True, allow_blank=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=10)


class RecommendationResultSerializer(serializers.Serializer):
    project = PrimaryProjectSerializer()
    score = serializers.FloatField()
    reason = serializers.CharField()


class RecommendationResponseSerializer(serializers.Serializer):
    items = RecommendationResultSerializer(many=True)
    mode = serializers.ChoiceField(
        choices=["semantic", "keyword-fallback"],
        help_text=(
            "semantic for successful ML integration, "
            "keyword-fallback for local keyword mode."
        ),
    )


class RecommendationReindexRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=False, default="manual_reindex")
    events = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        default=list,
    )


class RecommendationReindexResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
