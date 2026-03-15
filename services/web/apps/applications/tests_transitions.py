from uuid import uuid4

from apps.applications.models import Application, ApplicationStatus
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


def _make_project(owner, *, status=ProjectStatus.PUBLISHED, team_size=1):
    return Project.objects.create(
        title=f"Project {uuid4().hex[:8]}",
        owner=owner,
        status=status,
        team_size=team_size,
    )


def _make_application(project, applicant, *, status=ApplicationStatus.SUBMITTED):
    return Application.objects.create(project=project, applicant=applicant, status=status)


def test_application_create_forces_submitted_status():
    owner = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.PUBLISHED)

    client = Client()
    client.force_login(student)
    response = client.post(
        reverse("application-list"),
        data={"project": project.pk, "status": ApplicationStatus.ACCEPTED},
        content_type="application/json",
    )

    assert response.status_code == 201
    application = Application.objects.get(pk=response.json()["id"])
    assert application.status == ApplicationStatus.SUBMITTED


def test_application_create_rejected_for_non_catalog_project():
    owner = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.DRAFT)

    client = Client()
    client.force_login(student)
    response = client.post(
        reverse("application-list"),
        data={"project": project.pk},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "project" in response.json()


def test_project_owner_can_accept_application():
    owner = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.PUBLISHED, team_size=2)
    application = _make_application(project, student)

    client = Client()
    client.force_login(owner)
    response = client.post(
        reverse("application-review", kwargs={"pk": application.pk}),
        data={"decision": "accept"},
        content_type="application/json",
    )

    assert response.status_code == 200
    application.refresh_from_db()
    project.refresh_from_db()
    assert application.status == ApplicationStatus.ACCEPTED
    assert project.accepted_participants_count == 1
    assert project.status == ProjectStatus.PUBLISHED


def test_application_reject_requires_comment():
    owner = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.PUBLISHED)
    application = _make_application(project, student)

    client = Client()
    client.force_login(owner)
    response = client.post(
        reverse("application-review", kwargs={"pk": application.pk}),
        data={"decision": "reject", "comment": "short"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "comment" in response.json()


def test_application_review_forbidden_for_non_owner():
    owner = _make_user(role=UserRole.CUSTOMER)
    outsider = _make_user(role=UserRole.STUDENT)
    student = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.PUBLISHED)
    application = _make_application(project, student)

    client = Client()
    client.force_login(outsider)
    response = client.post(
        reverse("application-review", kwargs={"pk": application.pk}),
        data={"decision": "accept"},
        content_type="application/json",
    )

    assert response.status_code == 403


def test_project_becomes_staffed_when_team_is_full():
    owner = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.PUBLISHED, team_size=1)
    application = _make_application(project, student)

    client = Client()
    client.force_login(owner)
    response = client.post(
        reverse("application-review", kwargs={"pk": application.pk}),
        data={"decision": "accept"},
        content_type="application/json",
    )

    assert response.status_code == 200
    project.refresh_from_db()
    assert project.accepted_participants_count == 1
    assert project.status == ProjectStatus.STAFFED


def test_direct_application_status_patch_is_blocked():
    owner = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.PUBLISHED)
    application = _make_application(project, student)

    client = Client()
    client.force_login(student)
    response = client.patch(
        reverse("application-detail", kwargs={"pk": application.pk}),
        data={"status": ApplicationStatus.ACCEPTED},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "status" in response.json()
