from uuid import uuid4

from apps.notifications.models import Notification
from apps.projects.models import Project, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def _make_user(*, role: str | None = None):
    username = f"user-{uuid4().hex[:8]}"
    user = get_user_model().objects.create_user(
        username=username,
        password="placeholder",
    )
    if role is not None:
        UserProfile.objects.create(user=user, role=role)
    return user


def test_project_create_emits_notification_for_owner():
    owner = _make_user(role=UserRole.CUSTOMER)
    client = Client()
    client.force_login(owner)

    response = client.post(
        reverse("api-v1-project-list"),
        data={"title": f"Project {uuid4().hex[:8]}", "description": "Demo"},
        content_type="application/json",
    )
    assert response.status_code == 201

    project_id = response.json()["id"]
    project = Project.objects.get(pk=project_id)
    assert project.status == ProjectStatus.DRAFT

    assert Notification.objects.filter(
        recipient=owner,
        event_type="project.created",
        target_type="project",
        target_id=str(project_id),
    ).exists()


def test_project_update_emits_notification_for_owner():
    owner = _make_user(role=UserRole.CUSTOMER)
    project = Project.objects.create(
        title=f"Project {uuid4().hex[:8]}",
        owner=owner,
        status=ProjectStatus.DRAFT,
    )
    client = Client()
    client.force_login(owner)

    response = client.patch(
        reverse("api-v1-project-detail", kwargs={"pk": project.pk}),
        data={"description": "Updated"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert Notification.objects.filter(
        recipient=owner,
        event_type="project.updated",
        target_type="project",
        target_id=str(project.pk),
    ).exists()
