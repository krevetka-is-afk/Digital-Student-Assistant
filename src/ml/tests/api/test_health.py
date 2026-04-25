from starlette.testclient import TestClient

from src.ml.app.index_store import RecommendationIndexStore
from src.ml.app.models import OutboxEvent, ProjectPayload


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "ml"}



def test_ready_ok(client):
    r = client.get("/ready")
    assert r.status_code == 200
    payload = r.json()
    assert payload["mode"] == "stub-heuristic"
    assert payload["service"] == "ml"
    assert payload["projects_indexed"] == 0



def test_search_returns_ranked_projects_from_request_payload(client):
    response = client.post(
        "/search",
        json={
            "query": "graph",
            "projects": [
                {
                    "id": 1,
                    "title": "Graph analytics",
                    "description": "neo4j graph",
                    "tech_tags": ["graph"],
                },
                {
                    "id": 2,
                    "title": "Django API",
                    "description": "backend",
                    "tech_tags": ["django"],
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["project_id"] == 1



def test_search_prefers_local_index_when_outbox_state_exists(app_factory):
    index_store = RecommendationIndexStore(consumer="ml", state_path=None)
    index_store.project_event(
        OutboxEvent(
            id=10,
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id="11",
            payload={
                "pk": 11,
                "title": "Indexed graph project",
                "description": "graph embeddings",
                "tech_tags": ["graph", "embeddings"],
                "status": "published",
            },
        )
    )
    app = app_factory(index_store=index_store)
    with TestClient(app) as client:
        response = client.post(
            "/search",
            json={
                "query": "embeddings",
                "projects": [
                    ProjectPayload(
                        id=99,
                        title="Request payload project",
                        description="should be ignored when index is warm",
                        tech_tags=["request"],
                    ).model_dump()
                ],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "semantic"
    assert payload["items"][0]["project_id"] == 11



def test_recommendations_use_interest_overlap(client):
    response = client.post(
        "/recommendations",
        json={
            "interests": ["ml", "python"],
            "projects": [
                {
                    "id": 1,
                    "title": "Python ML ranking",
                    "description": "machine learning with python",
                    "tech_tags": ["python", "ml"],
                },
                {
                    "id": 2,
                    "title": "Django API",
                    "description": "backend",
                    "tech_tags": ["django"],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["project_id"] == 1



def test_reindex_accepts_requests(client):
    response = client.post(
        "/reindex",
        json={"reason": "manual", "events": [{"type": "project.changed"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["reindex_requests"] == 1
