from __future__ import annotations

from typing import Any

from starlette.testclient import TestClient


class ReadModelGraphStore:
    def setup_schema(self) -> None:
        return

    def ping(self) -> None:
        return

    def close(self) -> None:
        return

    def get_graph_meta(self, *, consumer: str) -> dict[str, Any]:
        return {
            "node_counts": {
                "student": 1,
                "project": 1,
                "supervisor": 1,
                "tag": 2,
                "application": 1,
            },
            "total_nodes": 6,
            "total_edges": 5,
            "available_node_types": [
                "application",
                "project",
                "student",
                "supervisor",
                "tag",
            ],
            "relationship_types": [
                "INTERESTED_IN",
                "SUBMITTED",
                "SUPERVISED_BY",
                "TAGGED_WITH",
                "TARGETS",
            ],
            "checkpoint_mirror": {
                "consumer": consumer,
                "last_acked_event_id": 12,
                "updated_at": "2026-04-19T14:00:00Z",
            },
        }

    def search_nodes(self, *, query: str, limit: int) -> list[dict[str, Any]]:
        assert query == "graph"
        assert limit == 2
        return [
            {
                "node_type": "project",
                "node_id": "11",
                "label": "Graph analytics assistant",
                "properties": {"status": "published", "score": 0.92},
            },
            {
                "node_type": "tag",
                "node_id": "graph",
                "label": "graph",
                "properties": {"score": 0.63},
            },
        ]

    def get_neighbors(self, *, node_type: str, node_id: str, limit: int) -> dict[str, Any]:
        assert node_type == "project"
        assert node_id == "11"
        assert limit == 10
        return {
            "focus": {"node_type": "project", "node_id": "11"},
            "nodes": [
                {
                    "node_type": "project",
                    "node_id": "11",
                    "label": "Graph analytics assistant",
                    "properties": {"status": "published"},
                },
                {
                    "node_type": "supervisor",
                    "node_id": "mentor@example.com",
                    "label": "mentor@example.com",
                    "properties": {"email": "mentor@example.com"},
                },
                {
                    "node_type": "tag",
                    "node_id": "graph",
                    "label": "graph",
                    "properties": {},
                },
            ],
            "edges": [
                {
                    "source_type": "project",
                    "source_id": "11",
                    "target_type": "supervisor",
                    "target_id": "mentor@example.com",
                    "relationship_type": "SUPERVISED_BY",
                },
                {
                    "source_type": "project",
                    "source_id": "11",
                    "target_type": "tag",
                    "target_id": "graph",
                    "relationship_type": "TAGGED_WITH",
                },
            ],
            "depth": 1,
        }

    def get_subgraph(
        self, *, node_type: str, node_id: str, depth: int
    ) -> dict[str, Any]:
        assert node_type == "student"
        assert node_id == "7"
        assert depth == 2
        return {
            "focus": {"node_type": "student", "node_id": "7"},
            "depth": depth,
            "nodes": [
                {
                    "node_type": "student",
                    "node_id": "7",
                    "label": "student-7",
                    "properties": {"username": "student-7"},
                },
                {
                    "node_type": "application",
                    "node_id": "50",
                    "label": "application-50",
                    "properties": {"status": "submitted"},
                },
                {
                    "node_type": "project",
                    "node_id": "11",
                    "label": "Graph analytics assistant",
                    "properties": {"status": "published"},
                },
            ],
            "edges": [
                {
                    "source_type": "student",
                    "source_id": "7",
                    "target_type": "application",
                    "target_id": "50",
                    "relationship_type": "SUBMITTED",
                },
                {
                    "source_type": "application",
                    "source_id": "50",
                    "target_type": "project",
                    "target_id": "11",
                    "relationship_type": "TARGETS",
                },
            ],
        }


class _CheckpointOnlyOutboxClient:
    async def get_checkpoint(self) -> dict[str, Any]:
        return {
            "consumer": "graph",
            "status": "active",
            "last_acked_event_id": 12,
            "last_seen_event_id": 12,
            "metadata": {},
        }

    async def fetch_events(
        self, *, mode: str, batch_size: int, replay_from_id: int | None = None
    ) -> list[dict[str, Any]]:
        return []

    async def ack_event(self, *, event_id: int) -> dict[str, Any]:
        return {"last_acked_event_id": event_id}


def _make_client(app_factory) -> TestClient:
    app = app_factory(
        graph_store=ReadModelGraphStore(),
        outbox_client=_CheckpointOnlyOutboxClient(),
    )
    return TestClient(app)


def test_graph_meta_returns_counts_and_relationship_overview(app_factory):
    with _make_client(app_factory) as client:
        response = client.get("/graph/meta")

    assert response.status_code == 200
    assert response.json() == {
        "node_counts": {
            "student": 1,
            "project": 1,
            "supervisor": 1,
            "tag": 2,
            "application": 1,
        },
        "total_nodes": 6,
        "total_edges": 5,
        "available_node_types": [
            "application",
            "project",
            "student",
            "supervisor",
            "tag",
        ],
        "relationship_types": [
            "INTERESTED_IN",
            "SUBMITTED",
            "SUPERVISED_BY",
            "TAGGED_WITH",
            "TARGETS",
        ],
        "checkpoint_mirror": {
            "consumer": "graph",
            "last_acked_event_id": 12,
            "updated_at": "2026-04-19T14:00:00Z",
        },
    }


def test_graph_search_returns_ranked_read_model_nodes(app_factory):
    with _make_client(app_factory) as client:
        response = client.get("/graph/search", params={"q": "graph", "limit": 2})

    assert response.status_code == 200
    assert response.json() == {
        "query": "graph",
        "limit": 2,
        "items": [
            {
                "node_type": "project",
                "node_id": "11",
                "label": "Graph analytics assistant",
                "properties": {"status": "published", "score": 0.92},
            },
            {
                "node_type": "tag",
                "node_id": "graph",
                "label": "graph",
                "properties": {"score": 0.63},
            },
        ],
    }


def test_graph_search_requires_query_string(app_factory):
    with _make_client(app_factory) as client:
        response = client.get("/graph/search")

    assert response.status_code == 422
    assert response.json()["detail"]


def test_graph_neighbors_returns_centered_one_hop_projection(app_factory):
    with _make_client(app_factory) as client:
        response = client.get("/graph/nodes/project/11/neighbors", params={"limit": 10})

    assert response.status_code == 200
    assert response.json() == {
        "focus": {"node_type": "project", "node_id": "11"},
        "depth": 1,
        "nodes": [
            {
                "node_type": "project",
                "node_id": "11",
                "label": "Graph analytics assistant",
                "properties": {"status": "published"},
            },
            {
                "node_type": "supervisor",
                "node_id": "mentor@example.com",
                "label": "mentor@example.com",
                "properties": {"email": "mentor@example.com"},
            },
            {
                "node_type": "tag",
                "node_id": "graph",
                "label": "graph",
                "properties": {},
            },
        ],
        "edges": [
            {
                "source_type": "project",
                "source_id": "11",
                "target_type": "supervisor",
                "target_id": "mentor@example.com",
                "relationship_type": "SUPERVISED_BY",
            },
            {
                "source_type": "project",
                "source_id": "11",
                "target_type": "tag",
                "target_id": "graph",
                "relationship_type": "TAGGED_WITH",
            },
        ],
    }


def test_graph_subgraph_returns_depth_bound_projection(app_factory):
    with _make_client(app_factory) as client:
        response = client.get(
            "/graph/subgraph",
            params={"node_type": "student", "node_id": "7", "depth": 2, "limit": 20},
        )

    assert response.status_code == 200
    assert response.json() == {
        "focus": {"node_type": "student", "node_id": "7"},
        "depth": 2,
        "nodes": [
            {
                "node_type": "student",
                "node_id": "7",
                "label": "student-7",
                "properties": {"username": "student-7"},
            },
            {
                "node_type": "application",
                "node_id": "50",
                "label": "application-50",
                "properties": {"status": "submitted"},
            },
            {
                "node_type": "project",
                "node_id": "11",
                "label": "Graph analytics assistant",
                "properties": {"status": "published"},
            },
        ],
        "edges": [
            {
                "source_type": "student",
                "source_id": "7",
                "target_type": "application",
                "target_id": "50",
                "relationship_type": "SUBMITTED",
            },
            {
                "source_type": "application",
                "source_id": "50",
                "target_type": "project",
                "target_id": "11",
                "relationship_type": "TARGETS",
            },
        ],
    }
