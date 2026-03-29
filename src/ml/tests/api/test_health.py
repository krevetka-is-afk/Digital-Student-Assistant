def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "ml"}


def test_ready_ok(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["mode"] == "stub-heuristic"


def test_search_returns_ranked_projects(client):
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


def test_reindex_accepts_requests(client):
    response = client.post(
        "/reindex",
        json={"reason": "manual", "events": [{"type": "project.changed"}]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
