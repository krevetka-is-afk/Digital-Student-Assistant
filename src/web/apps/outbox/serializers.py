from rest_framework import serializers

from .models import OutboxEvent


class OutboxEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboxEvent
        fields = [
            "id",
            "event_type",
            "aggregate_type",
            "aggregate_id",
            "source",
            "idempotency_key",
            "payload",
            "created_at",
        ]
