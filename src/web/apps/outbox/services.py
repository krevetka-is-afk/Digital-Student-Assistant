from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from .models import OutboxConsumerCheckpoint, OutboxEvent


def emit_event(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: int | str,
    payload: dict[str, Any],
    idempotency_key: str,
    source: str = "web",
) -> OutboxEvent:
    event, _ = OutboxEvent.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": str(aggregate_id),
            "payload": payload,
            "source": source,
        },
    )
    return event


def normalize_consumer_name(consumer: str) -> str:
    normalized = consumer.strip()
    if not normalized:
        raise ValueError("consumer must not be blank.")
    return normalized


def get_or_create_consumer_checkpoint(consumer: str) -> OutboxConsumerCheckpoint:
    normalized = normalize_consumer_name(consumer)
    checkpoint, _ = OutboxConsumerCheckpoint.objects.get_or_create(consumer=normalized)
    return checkpoint


def build_delivery_queryset(
    *,
    checkpoint: OutboxConsumerCheckpoint,
    event_type: str | None = None,
    since_id: int | None = None,
    mode: str = "poll",
    replay_from_id: int | None = None,
) -> QuerySet[OutboxEvent]:
    queryset = OutboxEvent.objects.all()
    if event_type:
        queryset = queryset.filter(event_type=event_type)

    if mode == "replay":
        lower_bound = max((replay_from_id or 1) - 1, 0)
    else:
        lower_bound = checkpoint.last_acked_event_id
        if since_id is not None:
            lower_bound = max(lower_bound, since_id)
    return queryset.filter(id__gt=lower_bound)


def mark_polled(
    *,
    checkpoint: OutboxConsumerCheckpoint,
    max_event_id: int | None,
) -> None:
    checkpoint.last_polled_at = timezone.now()
    if max_event_id is not None:
        checkpoint.last_seen_event_id = max(checkpoint.last_seen_event_id, max_event_id)
    checkpoint.save(update_fields=["last_polled_at", "last_seen_event_id", "updated_at"])


@transaction.atomic
def ack_event(*, consumer: str, event_id: int) -> tuple[OutboxConsumerCheckpoint, str]:
    normalized_consumer = normalize_consumer_name(consumer)
    checkpoint, _ = OutboxConsumerCheckpoint.objects.select_for_update().get_or_create(
        consumer=normalized_consumer
    )

    if event_id <= checkpoint.last_acked_event_id:
        return checkpoint, "already_acked"

    if not OutboxEvent.objects.filter(id=event_id).exists():
        raise OutboxEvent.DoesNotExist(f"Outbox event with id={event_id} does not exist.")

    checkpoint.last_acked_event_id = event_id
    checkpoint.last_acked_at = timezone.now()
    checkpoint.last_seen_event_id = max(checkpoint.last_seen_event_id, event_id)
    checkpoint.save(
        update_fields=["last_acked_event_id", "last_acked_at", "last_seen_event_id", "updated_at"]
    )
    return checkpoint, "advanced"
