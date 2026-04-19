from __future__ import annotations

from typing import Any

from .graph_store import GraphStore
from .models import GraphEvent, GraphNeighborsResponse, GraphNode, GraphSubgraphResponse
from .outbox_client import OutboxClient


class GraphProjector:
    def __init__(
        self,
        *,
        graph_store: GraphStore,
        outbox_client: OutboxClient,
        consumer: str,
    ):
        self._graph_store = graph_store
        self._outbox_client = outbox_client
        self._consumer = consumer

    async def read_checkpoint(self) -> dict[str, Any]:
        return await self._outbox_client.get_checkpoint()

    def project_events(self, events: list[GraphEvent]) -> dict[str, int | None]:
        processed = 0
        last_event_id: int | None = None

        for event in events:
            self._graph_store.project_event(event)
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
            self._graph_store.set_checkpoint_mirror(
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
        return self._graph_store.get_state_summary(consumer=self._consumer)

    def meta(self) -> dict[str, Any]:
        return self._graph_store.get_graph_meta(consumer=self._consumer)

    def search(self, *, query: str, limit: int) -> list[GraphNode]:
        return self._graph_store.search_nodes(query=query, limit=limit)

    def neighbors(self, *, node_type: str, node_id: str, limit: int) -> GraphNeighborsResponse:
        return self._graph_store.get_neighbors(node_type=node_type, node_id=node_id, limit=limit)

    def subgraph(self, *, node_type: str, node_id: str, depth: int) -> GraphSubgraphResponse:
        return self._graph_store.get_subgraph(node_type=node_type, node_id=node_id, depth=depth)
