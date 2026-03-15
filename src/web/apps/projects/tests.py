import json
from datetime import timedelta
from uuid import uuid4

from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone


def test_project_defaults():
    project = Project(title="Data platform")

    assert project.status == ProjectStatus.DRAFT
    assert project.source_type == ProjectSourceType.MANUAL
    assert project.tech_tags == []


def _make_user():
    username = f"owner-{uuid4().hex[:8]}"
    return get_user_model().objects.create_user(username=username, password="test-pass-123")


def _title(prefix: str) -> str:
    return f"{prefix} {uuid4().hex[:8]}"


def test_create_project_defaults_extra_data_when_missing():
    user = _make_user()
    client = Client()
    client.force_login(user)

    response = client.post(
        reverse("api-v1-project-list"),
        data=json.dumps({"title": _title("Project without extra data")}),
        content_type="application/json",
    )

    assert response.status_code == 201
    project = Project.objects.get(pk=response.json()["pk"])
    assert project.extra_data == {}
    assert response.json()["extra_data"] == {}


def test_create_project_normalizes_null_extra_data():
    user = _make_user()
    client = Client()
    client.force_login(user)

    response = client.post(
        reverse("api-v1-project-list"),
        data=json.dumps({"title": _title("Project with null extra data"), "extra_data": None}),
        content_type="application/json",
    )

    assert response.status_code == 201
    project = Project.objects.get(pk=response.json()["pk"])
    assert project.extra_data == {}
    assert response.json()["extra_data"] == {}


def test_create_project_normalizes_null_tech_tags():
    user = _make_user()
    client = Client()
    client.force_login(user)

    response = client.post(
        reverse("api-v1-project-list"),
        data=json.dumps({"title": _title("Project with null tech tags"), "tech_tags": None}),
        content_type="application/json",
    )

    assert response.status_code == 201
    project = Project.objects.get(pk=response.json()["pk"])
    assert project.tech_tags == {}
    assert response.json()["tech_tags"] == {}


def _make_project(
    title: str,
    *,
    owner=None,
    status: str = ProjectStatus.PUBLISHED,
    description: str = "",
) -> Project:
    return Project.objects.create(
        title=title,
        owner=owner,
        status=status,
        description=description,
    )


def test_projects_list_returns_paginated_shape_and_page_size():
    user = _make_user()
    for i in range(12):
        _make_project(
            title=_title(f"Paginated project {i}"),
            owner=user,
            status=ProjectStatus.DRAFT,
        )

    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("api-v1-project-list"),
        data={"page": 1, "page_size": 5, "status": ProjectStatus.DRAFT},
    )

    assert response.status_code == 200
    payload = response.json()
    assert {"count", "results"}.issubset(payload.keys())
    assert payload["count"] == 12
    assert len(payload["results"]) == 5


def test_projects_list_page_size_is_capped():
    user = _make_user()
    for i in range(120):
        _make_project(
            title=_title(f"Large page project {i}"),
            owner=user,
            status=ProjectStatus.DRAFT,
        )

    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("api-v1-project-list"),
        data={"status": ProjectStatus.DRAFT, "page_size": 200},
    )

    assert response.status_code == 200
    assert len(response.json()["results"]) == 100


def test_projects_list_filters_by_status():
    user = _make_user()
    other = _make_user()
    own_draft = _make_project(
        title=_title("Own draft"),
        owner=user,
        status=ProjectStatus.DRAFT,
    )
    _make_project(
        title=_title("Other draft"),
        owner=other,
        status=ProjectStatus.DRAFT,
    )
    _make_project(
        title=_title("Public project"),
        owner=other,
        status=ProjectStatus.PUBLISHED,
    )

    client = Client()
    client.force_login(user)
    response = client.get(reverse("api-v1-project-list"), data={"status": ProjectStatus.DRAFT})

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["pk"] == own_draft.pk
    assert results[0]["status"] == ProjectStatus.DRAFT


def test_projects_list_searches_by_title_q():
    token = uuid4().hex[:8]
    matching = _make_project(title=f"ML Vision {token}")
    _make_project(title=_title("Backend Service"))

    client = Client()
    response = client.get(reverse("api-v1-project-list"), data={"q": token})

    assert response.status_code == 200
    results = response.json()["results"]
    assert any(item["pk"] == matching.pk for item in results)
    assert all(token in item["title"] for item in results)


def test_projects_list_orders_by_created_at():
    user = _make_user()
    older = _make_project(title=_title("Older"), owner=user, status=ProjectStatus.DRAFT)
    newer = _make_project(title=_title("Newer"), owner=user, status=ProjectStatus.DRAFT)
    now = timezone.now()
    Project.objects.filter(pk=older.pk).update(created_at=now - timedelta(days=3))
    Project.objects.filter(pk=newer.pk).update(created_at=now - timedelta(days=1))

    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("api-v1-project-list"),
        data={"ordering": "created_at", "page_size": 10, "status": ProjectStatus.DRAFT},
    )

    assert response.status_code == 200
    ordered_ids = [item["pk"] for item in response.json()["results"]]
    assert ordered_ids.index(older.pk) < ordered_ids.index(newer.pk)


def test_projects_list_orders_by_updated_at_desc():
    user = _make_user()
    older = _make_project(
        title=_title("Updated older"),
        owner=user,
        status=ProjectStatus.DRAFT,
    )
    newer = _make_project(
        title=_title("Updated newer"),
        owner=user,
        status=ProjectStatus.DRAFT,
    )
    now = timezone.now()
    Project.objects.filter(pk=older.pk).update(updated_at=now - timedelta(days=2))
    Project.objects.filter(pk=newer.pk).update(updated_at=now)

    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("api-v1-project-list"),
        data={"ordering": "-updated_at", "page_size": 10, "status": ProjectStatus.DRAFT},
    )

    assert response.status_code == 200
    ordered_ids = [item["pk"] for item in response.json()["results"]]
    assert ordered_ids.index(newer.pk) < ordered_ids.index(older.pk)


def test_projects_list_returns_400_for_invalid_status():
    _make_project(title=_title("Any project"))
    client = Client()
    response = client.get(reverse("api-v1-project-list"), data={"status": "unknown"})

    assert response.status_code == 400
    assert "status" in response.json()


def test_projects_list_returns_400_for_invalid_ordering():
    _make_project(title=_title("Any project"))
    client = Client()
    response = client.get(reverse("api-v1-project-list"), data={"ordering": "title"})

    assert response.status_code == 400
    assert "ordering" in response.json()


def test_projects_list_is_query_efficient():
    owner = _make_user()
    for i in range(8):
        _make_project(title=_title(f"Perf project {i}"), owner=owner)

    client = Client()
    with CaptureQueriesContext(connection) as query_context:
        response = client.get(reverse("api-v1-project-list"), data={"page_size": 5})

    assert response.status_code == 200
    assert len(query_context.captured_queries) <= 4
