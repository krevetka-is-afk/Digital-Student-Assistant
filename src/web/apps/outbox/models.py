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
