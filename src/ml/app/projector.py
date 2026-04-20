from __future__ import annotations

from typing import Any

from .index_store import RecommendationIndexStore
from .models import OutboxEvent
from .outbox_client import OutboxClient


class MLProjector:
    def __init__(
        self,
        *,
        index_store: RecommendationIndexStore,
        outbox_client: OutboxClient,
        consumer: str,
    ):
        self._index_store = index_store
        self._outbox_client = outbox_client
        self._consumer = consumer

    async def read_checkpoint(self) -> dict[str, Any]:
        return await self._outbox_client.get_checkpoint()

    def project_events(self, events: list[OutboxEvent]) -> dict[str, int | None]:
        processed = 0
        last_event_id: int | None = None

        for event in events:
            self._index_store.project_event(event)
            processed += 1
            if event.id is not None:
                last_event_id = max(last_event_id or 0, int(event.id))

        return {
            "processed": processed,
            "last_event_id": last_event_id,
        }

    async def sync_from_outbox(
        self,
        *,
        mode: str,
        batch_size: int,
        replay_from_id: int | None = None,
    ) -> dict[str, Any]:
        events = await self._outbox_client.fetch_events(
            mode=mode,
            batch_size=batch_size,
            replay_from_id=replay_from_id,
        )
        projection = self.project_events(events)
        last_event_id = projection["last_event_id"]
        ack_payload: dict[str, Any] | None = None
        if last_event_id is not None:
            ack_payload = await self._outbox_client.ack_event(event_id=last_event_id)
            self._index_store.set_checkpoint_mirror(
                consumer=self._consumer,
                last_acked_event_id=int(last_event_id),
            )

        return {
            "mode": mode,
            "processed": projection["processed"],
            "last_event_id": last_event_id,
            "ack": ack_payload,
        }

    def state_summary(self) -> dict[str, Any]:
        return self._index_store.get_state_summary(consumer=self._consumer)
