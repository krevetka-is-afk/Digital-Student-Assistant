from uuid import uuid4

from apps.projects.models import Project, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def _make_user(*, role: str | None = None, is_staff: bool = False):
    username = f"user-{uuid4().hex[:8]}"
    user = get_user_model().objects.create_user(
        username=username,
        password="test-pass-123",
        is_staff=is_staff,
    )
    if role is not None:
        UserProfile.objects.create(user=user, role=role)
    return user


def _make_project(owner, *, status=ProjectStatus.DRAFT):
    return Project.objects.create(title=f"Project {uuid4().hex[:8]}", owner=owner, status=status)


def test_owner_can_submit_project_for_moderation():
    owner = _make_user(role=UserRole.CUSTOMER)
    project = _make_project(owner, status=ProjectStatus.DRAFT)
    client = Client()
    client.force_login(owner)

    response = client.post(reverse("api-v1-project-submit", kwargs={"pk": project.pk}))

    assert response.status_code == 200
    project.refresh_from_db()
    assert project.status == ProjectStatus.ON_MODERATION


def test_project_submit_requires_owner_or_staff():
    owner = _make_user(role=UserRole.CUSTOMER)
    outsider = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.DRAFT)
    client = Client()
    client.force_login(outsider)

    response = client.post(reverse("api-v1-project-submit", kwargs={"pk": project.pk}))

    assert response.status_code == 403


def test_cpprp_can_approve_project_on_moderation():
    owner = _make_user(role=UserRole.CUSTOMER)
    cpprp = _make_user(role=UserRole.CPPRP)
    project = _make_project(owner, status=ProjectStatus.ON_MODERATION)
    client = Client()
    client.force_login(cpprp)

    response = client.post(
        reverse("api-v1-project-moderate", kwargs={"pk": project.pk}),
        data={"decision": "approve"},
        content_type="application/json",
    )

    assert response.status_code == 200
    project.refresh_from_db()
    assert project.status == ProjectStatus.PUBLISHED
    assert project.moderated_by_id == cpprp.id


def test_project_reject_requires_comment():
    owner = _make_user(role=UserRole.CUSTOMER)
    cpprp = _make_user(role=UserRole.CPPRP)
    project = _make_project(owner, status=ProjectStatus.ON_MODERATION)
    client = Client()
    client.force_login(cpprp)

    response = client.post(
        reverse("api-v1-project-moderate", kwargs={"pk": project.pk}),
        data={"decision": "reject", "comment": "too short"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "comment" in response.json()


def test_direct_project_status_patch_is_blocked():
    owner = _make_user(role=UserRole.CUSTOMER)
    project = _make_project(owner, status=ProjectStatus.DRAFT)
    client = Client()
    client.force_login(owner)

    response = client.patch(
        reverse("api-v1-project-detail", kwargs={"pk": project.pk}),
        data={"status": ProjectStatus.PUBLISHED},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "status" in response.json()
