from __future__ import annotations

from typing import Any, TypedDict, cast

from app.index_store import RecommendationIndexStore
from app.models import OutboxEvent
from starlette.testclient import TestClient


class _CheckpointState(TypedDict):
    consumer: str
    status: str
    last_acked_event_id: int
    last_seen_event_id: int
    metadata: dict[str, Any]


class FakeOutboxClient:
    def __init__(self, *, events: list[OutboxEvent], initial_checkpoint: int = 0):
        self._events = sorted(events, key=lambda event: event.id or 0)
        self._checkpoint: _CheckpointState = {
            "consumer": "ml",
            "status": "active",
            "last_acked_event_id": initial_checkpoint,
            "last_seen_event_id": initial_checkpoint,
            "metadata": {},
        }
        self.calls: list[dict[str, Any]] = []

    async def get_checkpoint(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._checkpoint.copy())

    async def fetch_events(
        self,
        *,
        mode: str,
        batch_size: int,
        replay_from_id: int | None = None,
    ) -> list[OutboxEvent]:
        self.calls.append(
            {
                "mode": mode,
                "batch_size": batch_size,
                "replay_from_id": replay_from_id,
            }
        )

        if mode == "replay":
            lower_bound = max((replay_from_id or 1) - 1, 0)
        else:
            lower_bound = self._checkpoint["last_acked_event_id"]

        return [event for event in self._events if (event.id or 0) > lower_bound][:batch_size]

    async def ack_event(self, *, event_id: int) -> dict[str, Any]:
        if event_id <= self._checkpoint["last_acked_event_id"]:
            status = "already_acked"
        else:
            status = "advanced"
            self._checkpoint["last_acked_event_id"] = event_id
        self._checkpoint["last_seen_event_id"] = max(
            self._checkpoint["last_seen_event_id"], event_id
        )
        return {
            "ack_status": status,
            **self._checkpoint,
        }



def _make_client(app_factory, *, events: list[OutboxEvent], initial_checkpoint: int = 0):
    index_store = RecommendationIndexStore(consumer="ml", state_path=None)
    outbox_client = FakeOutboxClient(events=events, initial_checkpoint=initial_checkpoint)
    app = app_factory(index_store=index_store, outbox_client=outbox_client)
    return TestClient(app), index_store, outbox_client



def test_sync_uses_outbox_poll_and_populates_local_index(app_factory):
    client, index_store, outbox_client = _make_client(
        app_factory,
        events=[
            OutboxEvent(
                id=11,
                event_type="project.changed",
                aggregate_type="project",
                aggregate_id="11",
                payload={
                    "pk": 11,
                    "title": "Outbox indexed project",
                    "description": "semantic graph search",
                    "tech_tags": ["graph", "search"],
                    "supervisor_name": "Dr. Neo",
                    "source_type": "initiative",
                    "status": "published",
                },
            ),
            OutboxEvent(
                id=12,
                event_type="user_profile.changed",
                aggregate_type="user_profile",
                aggregate_id="7",
                payload={
                    "id": 7,
                    "role": "student",
                    "interests": ["graph", "ml"],
                },
            ),
        ],
    )
    with client:
        response = client.post("/sync", json={"batch_size": 50})
        assert response.status_code == 200
        payload = response.json()
        assert payload["processed"] == 2
        assert payload["last_event_id"] == 12
        assert payload["ack"]["last_acked_event_id"] == 12
        assert outbox_client.calls == [{"mode": "poll", "batch_size": 50, "replay_from_id": None}]

        state = client.get("/state")
        assert state.status_code == 200
        body = state.json()
        assert body["projects_indexed"] == 1
        assert body["profiles_indexed"] == 1
        assert body["checkpoint_mirror"]["last_acked_event_id"] == 12

        search = client.post("/search", json={"query": "semantic", "projects": []})
        assert search.status_code == 200
        assert search.json()["mode"] == "semantic"
        assert search.json()["items"][0]["project_id"] == 11



def test_replay_mode_reprocesses_from_offset_and_acks(app_factory):
    client, _, outbox_client = _make_client(
        app_factory,
        events=[
            OutboxEvent(
                id=3,
                event_type="project.changed",
                aggregate_type="project",
                aggregate_id="3",
                payload={
                    "pk": 3,
                    "title": "Legacy item",
                    "description": "older project",
                    "tech_tags": ["legacy"],
                    "status": "published",
                },
            ),
            OutboxEvent(
                id=8,
                event_type="project.changed",
                aggregate_type="project",
                aggregate_id="8",
                payload={
                    "pk": 8,
                    "title": "New item",
                    "description": "newer project",
                    "tech_tags": ["fresh"],
                    "status": "published",
                },
            ),
        ],
        initial_checkpoint=8,
    )
    with client:
        response = client.post("/replay", json={"replay_from_id": 3, "batch_size": 10})
        assert response.status_code == 200
        payload = response.json()
        assert payload["replayed"] == 2
        assert payload["last_event_id"] == 8
        assert payload["ack"]["ack_status"] == "already_acked"
        assert outbox_client.calls == [{"mode": "replay", "batch_size": 10, "replay_from_id": 3}]



def test_ready_reports_checkpoint_and_degraded_outbox_status(app_factory):
    class BrokenOutboxClient:
        async def get_checkpoint(self) -> dict[str, Any]:
            raise RuntimeError("boom")

        async def fetch_events(
            self, *, mode: str, batch_size: int, replay_from_id: int | None = None
        ):
            return []

        async def ack_event(self, *, event_id: int) -> dict[str, Any]:
            return {}

    app = app_factory(outbox_client=BrokenOutboxClient())
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["outbox"] == "error:RuntimeError"


def test_project_deleted_event_removes_item_from_local_index(app_factory):
    client, _, _ = _make_client(
        app_factory,
        events=[
            OutboxEvent(
                id=1,
                event_type="project.changed",
                aggregate_type="project",
                aggregate_id="15",
                payload={
                    "pk": 15,
                    "title": "To remove",
                    "tech_tags": ["ml"],
                    "status": "published",
                },
            ),
            OutboxEvent(
                id=2,
                event_type="project.deleted",
                aggregate_type="project",
                aggregate_id="15",
                payload={"pk": 15, "status": "deleted", "tombstone": True},
            ),
        ],
    )
    with client:
        response = client.post("/sync", json={"batch_size": 10})
        state = client.get("/state")

    assert response.status_code == 200
    assert state.status_code == 200
    assert state.json()["projects_indexed"] == 0
