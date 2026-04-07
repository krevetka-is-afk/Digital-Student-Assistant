from django.db import models


class OutboxEvent(models.Model):
    event_type = models.CharField(max_length=100, db_index=True)
    aggregate_type = models.CharField(max_length=100, db_index=True)
    aggregate_id = models.CharField(max_length=100, db_index=True)
    source = models.CharField(max_length=100, default="web")
    idempotency_key = models.CharField(max_length=255, unique=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.aggregate_type}:{self.aggregate_id}"


class OutboxConsumerCheckpoint(models.Model):
    class DeliveryStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"

    consumer = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.ACTIVE,
        db_index=True,
    )
    last_acked_event_id = models.BigIntegerField(default=0)
    last_seen_event_id = models.BigIntegerField(default=0)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    last_acked_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["consumer"]

    def __str__(self) -> str:
        return f"{self.consumer}:{self.last_acked_event_id}"
