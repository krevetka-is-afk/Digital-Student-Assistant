from uuid import uuid4

from apps.projects.models import Project, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def _make_student(*, interests=None):
    user = get_user_model().objects.create_user(
        username=f"student-recs-{uuid4().hex[:8]}",
        password="pass123456",
    )
    UserProfile.objects.create(
        user=user,
        role=UserRole.STUDENT,
        interests=interests or ["python", "ml"],
    )
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
    assert payload["mode"] == "local-fallback"
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
    assert response.json()["items"][0]["project"]["title"] == "Graph analytics"
