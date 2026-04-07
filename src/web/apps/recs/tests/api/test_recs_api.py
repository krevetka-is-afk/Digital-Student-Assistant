from unittest.mock import Mock, patch
from uuid import uuid4

import requests
from apps.projects.models import Project, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def _make_student(*, interests=None):
    user = get_user_model().objects.create_user(
        username=f"student-recs-{uuid4().hex[:8]}",
        password="placeholder",
    )
    UserProfile.objects.create(
        user=user,
        role=UserRole.STUDENT,
        interests=interests or ["python", "ml"],
    )
    return user


def _make_cpprp():
    user = get_user_model().objects.create_user(
        username=f"cpprp-recs-{uuid4().hex[:8]}",
        password="placeholder",
    )
    UserProfile.objects.create(user=user, role=UserRole.CPPRP)
    return user


def test_recommendations_endpoint_returns_local_fallback_results():
    token = f"focus-{uuid4().hex[:8]}"
    Project.objects.create(
        title=f"Python ML ranking {token}",
        description=f"machine learning with python {token}",
        status=ProjectStatus.PUBLISHED,
        tech_tags=["python", token],
    )
    client = Client()
    client.force_login(_make_student(interests=[token]))

    response = client.get(reverse("api-v1-recs-recommendations"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "keyword-fallback"
    titles = [item["project"]["title"] for item in payload["items"]]
    assert f"Python ML ranking {token}" in titles


def test_recs_search_endpoint_returns_ranked_projects():
    Project.objects.create(
        title="Graph analytics",
        description="neo4j and graph recommendations",
        status=ProjectStatus.PUBLISHED,
        tech_tags=["neo4j", "graph"],
    )
    client = Client()

    response = client.get(reverse("api-v1-recs-search"), data={"q": "graph"})

    assert response.status_code == 200
    assert response.json()["mode"] == "keyword-fallback"
    assert response.json()["items"][0]["project"]["title"] == "Graph analytics"


def test_recs_search_endpoint_uses_remote_ml_service(monkeypatch):
    project = Project.objects.create(
        title="Graph analytics",
        description="neo4j and graph recommendations",
        status=ProjectStatus.PUBLISHED,
        tech_tags=["neo4j", "graph"],
    )
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.example")

    remote_response = Mock()
    remote_response.raise_for_status.return_value = None
    remote_response.json.return_value = {
        "mode": "semantic",
        "items": [
            {
                "project_id": project.pk,
                "score": 0.98,
                "reason": "semantic similarity",
            }
        ],
    }

    with patch("apps.recs.services.requests.post", return_value=remote_response) as post_mock:
        response = Client().get(reverse("api-v1-recs-search"), data={"q": "graph databases"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "semantic"
    assert payload["items"][0]["project"]["pk"] == project.pk
    assert payload["items"][0]["reason"] == "semantic similarity"
    assert post_mock.call_args.args[0] == "http://ml.example/search"


def test_recommendations_endpoint_uses_remote_ml_service(monkeypatch):
    token = f"remote-{uuid4().hex[:8]}"
    project = Project.objects.create(
        title=f"Semantic match {token}",
        description=f"vector retrieval {token}",
        status=ProjectStatus.PUBLISHED,
        tech_tags=["embedding", token],
    )
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.example")
    client = Client()
    client.force_login(_make_student(interests=[token]))

    remote_response = Mock()
    remote_response.raise_for_status.return_value = None
    remote_response.json.return_value = {
        "mode": "semantic",
        "items": [
            {
                "project_id": project.pk,
                "score": 0.91,
                "reason": "semantic recommendation",
            }
        ],
    }

    with patch("apps.recs.services.requests.post", return_value=remote_response):
        response = client.get(reverse("api-v1-recs-recommendations"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "semantic"
    assert payload["items"][0]["project"]["title"] == f"Semantic match {token}"
    assert payload["items"][0]["score"] == 0.91


def test_recommendations_endpoint_falls_back_on_ml_timeout(monkeypatch):
    token = f"timeout-{uuid4().hex[:8]}"
    Project.objects.create(
        title=f"Timeout fallback {token}",
        description=f"machine learning with python {token}",
        status=ProjectStatus.PUBLISHED,
        tech_tags=["python", token],
    )
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.example")
    client = Client()
    client.force_login(_make_student(interests=[token]))

    with patch("apps.recs.services.requests.post", side_effect=requests.Timeout):
        response = client.get(reverse("api-v1-recs-recommendations"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "keyword-fallback"
    titles = [item["project"]["title"] for item in payload["items"]]
    assert f"Timeout fallback {token}" in titles


def test_recs_search_endpoint_falls_back_on_ml_timeout(monkeypatch):
    token = f"search-timeout-{uuid4().hex[:8]}"
    Project.objects.create(
        title=f"Search timeout fallback {token}",
        description=f"semantic search fallback {token}",
        status=ProjectStatus.PUBLISHED,
        tech_tags=["search", token],
    )
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.example")

    with patch("apps.recs.services.requests.post", side_effect=requests.Timeout):
        response = Client().get(reverse("api-v1-recs-search"), data={"q": token})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "keyword-fallback"
    titles = [item["project"]["title"] for item in payload["items"]]
    assert f"Search timeout fallback {token}" in titles


def test_recs_search_endpoint_falls_back_on_invalid_ml_payload(monkeypatch):
    token = f"invalid-payload-{uuid4().hex[:8]}"
    Project.objects.create(
        title=f"Invalid payload fallback {token}",
        description=f"search fallback {token}",
        status=ProjectStatus.PUBLISHED,
        tech_tags=["search", token],
    )
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.example")

    remote_response = Mock()
    remote_response.raise_for_status.return_value = None
    remote_response.json.return_value = {
        "mode": "semantic",
        "items": [{"unexpected": "shape"}],
    }

    with patch("apps.recs.services.requests.post", return_value=remote_response):
        response = Client().get(reverse("api-v1-recs-search"), data={"q": token})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "keyword-fallback"
    titles = [item["project"]["title"] for item in payload["items"]]
    assert f"Invalid payload fallback {token}" in titles


def test_only_cpprp_can_request_reindex():
    client = Client()
    client.force_login(_make_student())

    denied = client.post(
        reverse("api-v1-recs-reindex"),
        data={"reason": "student"},
        content_type="application/json",
    )

    assert denied.status_code == 403

    client.force_login(_make_cpprp())
    allowed = client.post(
        reverse("api-v1-recs-reindex"),
        data={"reason": "cpprp"},
        content_type="application/json",
    )

    assert allowed.status_code == 200
    assert allowed.json()["status"] == "accepted"
