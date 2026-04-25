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
        password="placeholder",
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


def test_customer_cannot_create_application():
    owner = _make_user(role=UserRole.CUSTOMER)
    customer = _make_user(role=UserRole.CUSTOMER)
    project = _make_project(owner, status=ProjectStatus.PUBLISHED)

    client = Client()
    client.force_login(customer)
    response = client.post(
        reverse("application-list"),
        data={"project": project.pk},
        content_type="application/json",
    )

    assert response.status_code == 403


def test_customer_cannot_list_applications_from_student_endpoint():
    customer = _make_user(role=UserRole.CUSTOMER)
    client = Client()
    client.force_login(customer)

    response = client.get(reverse("application-list"))

    assert response.status_code == 403


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


def test_application_reject_comment_minimum_length_matches_bpmn():
    owner = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.PUBLISHED)
    application = _make_application(project, student)

    client = Client()
    client.force_login(owner)

    too_short_comment = "x" * 49
    short_response = client.post(
        reverse("application-review", kwargs={"pk": application.pk}),
        data={"decision": "reject", "comment": too_short_comment},
        content_type="application/json",
    )
    assert short_response.status_code == 400
    assert "comment" in short_response.json()

    bpmn_min_comment = "x" * 50
    ok_response = client.post(
        reverse("application-review", kwargs={"pk": application.pk}),
        data={"decision": "reject", "comment": bpmn_min_comment},
        content_type="application/json",
    )
    assert ok_response.status_code == 200
    assert ok_response.json()["status"] == ApplicationStatus.REJECTED


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


def test_student_owner_cannot_review_application():
    owner = _make_user(role=UserRole.STUDENT)
    student = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.PUBLISHED)
    application = _make_application(project, student)

    client = Client()
    client.force_login(owner)
    response = client.post(
        reverse("application-review", kwargs={"pk": application.pk}),
        data={"decision": "accept"},
        content_type="application/json",
    )

    assert response.status_code == 403


def test_cpprp_cannot_review_application():
    owner = _make_user(role=UserRole.CUSTOMER)
    cpprp = _make_user(role=UserRole.CPPRP)
    student = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.PUBLISHED)
    application = _make_application(project, student)

    client = Client()
    client.force_login(cpprp)
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


def test_application_delete_emits_tombstone_event():
    owner = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    project = _make_project(owner, status=ProjectStatus.PUBLISHED)
    application = _make_application(project, student)

    client = Client()
    client.force_login(student)
    response = client.delete(reverse("application-detail", kwargs={"pk": application.pk}))

    assert response.status_code == 204
    assert Application.objects.filter(pk=application.pk).exists() is False

    from apps.outbox.models import OutboxEvent

    event = OutboxEvent.objects.order_by("-id").first()
    assert event is not None
    assert event.event_type == "application.deleted"
    assert event.payload["id"] == application.pk
    assert event.payload["tombstone"] is True
