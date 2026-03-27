from __future__ import annotations

from typing import Any

from .models import OutboxEvent


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
