def test_health_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "graph"}


def test_projector_accepts_project_and_profile_events(client):
    response = client.post(
        "/project",
        json={
            "events": [
                {
                    "event_type": "project.changed",
                    "aggregate_type": "project",
                    "aggregate_id": "1",
                    "payload": {
                        "pk": 1,
                        "supervisor_email": "mentor@example.com",
                        "tech_tags": ["python", "ml"],
                    },
                },
                {
                    "event_type": "user_profile.changed",
                    "aggregate_type": "user_profile",
                    "aggregate_id": "7",
                    "payload": {"id": 7, "interests": ["ml"]},
                },
            ]
        },
    )
    state = client.get("/state")

    assert response.status_code == 200
    assert state.status_code == 200
    assert state.json()["nodes"]["project"] >= 1
    assert state.json()["nodes"]["tag"] >= 1
