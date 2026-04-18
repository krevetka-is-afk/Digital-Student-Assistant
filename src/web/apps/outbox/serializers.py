from rest_framework import serializers

from .models import OutboxConsumerCheckpoint, OutboxEvent


class OutboxEventSerializer(serializers.ModelSerializer):
    delivery_status = serializers.SerializerMethodField()

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
            "delivery_status",
        ]

    def get_delivery_status(self, obj) -> str | None:
        checkpoint_id = self.context.get("checkpoint_id")
        if checkpoint_id is None:
            return None
        return "acked" if obj.id <= checkpoint_id else "pending"


class OutboxAckSerializer(serializers.Serializer):
    consumer = serializers.CharField(max_length=100)
    event_id = serializers.IntegerField(min_value=1)

    def validate_consumer(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("consumer must not be blank.")
        return normalized


class OutboxConsumerCheckpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboxConsumerCheckpoint
        fields = [
            "consumer",
            "status",
            "last_acked_event_id",
            "last_seen_event_id",
            "last_polled_at",
            "last_acked_at",
            "metadata",
            "created_at",
            "updated_at",
        ]


class OutboxAckResponseSerializer(OutboxConsumerCheckpointSerializer):
    ack_status = serializers.ChoiceField(choices=["advanced", "already_acked"])

    class Meta(OutboxConsumerCheckpointSerializer.Meta):
        fields = ["ack_status", *OutboxConsumerCheckpointSerializer.Meta.fields]
