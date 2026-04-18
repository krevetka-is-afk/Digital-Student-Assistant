from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from django.db import models

class OutboxEvent(models.Model):
    objects: ClassVar[models.Manager[OutboxEvent]]
    _meta: ClassVar[Any]
    DoesNotExist: ClassVar[type[Exception]]

    id: int
    pk: int | None
    event_type: str
    aggregate_type: str
    aggregate_id: str
    source: str
    idempotency_key: str
    payload: dict[str, object]
    created_at: datetime

    def __str__(self) -> str: ...


class OutboxConsumerCheckpoint(models.Model):
    objects: ClassVar[models.Manager[OutboxConsumerCheckpoint]]
    _meta: ClassVar[Any]

    class DeliveryStatus(models.TextChoices):
        ACTIVE: ClassVar[str]
        PAUSED: ClassVar[str]
        values: ClassVar[list[str]]

    id: int
    pk: int | None
    consumer: str
    status: str
    last_acked_event_id: int
    last_seen_event_id: int
    last_polled_at: datetime | None
    last_acked_at: datetime | None
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str: ...
