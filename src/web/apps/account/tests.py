from uuid import uuid4

from apps.account.models import DeadlineAudience, DocumentTemplate, PlatformDeadline
from apps.applications.models import Application, ApplicationStatus
from apps.projects.models import EPP, Project, ProjectSourceType, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def _make_user(*, role: str, is_staff: bool = False):
    username = f"user-{uuid4().hex[:8]}"
    user = get_user_model().objects.create_user(
        username=username,
        password="test-pass-123",
        is_staff=is_staff,
        email=f"{username}@example.com",
    )
    UserProfile.objects.create(user=user, role=role)
    return user


def _make_epp() -> EPP:
    return EPP.objects.create(
        source_ref=f"epp-{uuid4().hex[:6]}",
        title="Imported EPP",
        campaign_title="Spring 2026",
        status_raw="Опубликована",
    )


def _make_project(owner, epp: EPP, *, status=ProjectStatus.PUBLISHED):
    return Project.objects.create(
        title=f"Project {uuid4().hex[:8]}",
        owner=owner,
        epp=epp,
        source_type=ProjectSourceType.EPP,
        source_ref=uuid4().hex,
        status=status,
        status_raw="Опубликована",
    )


def _make_application(project, applicant, *, status=ApplicationStatus.SUBMITTED):
    return Application.objects.create(project=project, applicant=applicant, status=status)


def test_account_me_returns_profile_and_counters():
    student = _make_user(role=UserRole.STUDENT)
    epp = _make_epp()
    project = _make_project(student, epp, status=ProjectStatus.ON_MODERATION)
    _make_application(project, student)

    client = Client()
    client.force_login(student)
    response = client.get(reverse("account-me"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["role"] == UserRole.STUDENT
    assert payload["counters"]["applications_total"] == 1
    assert payload["counters"]["projects_total"] == 1


def test_account_student_overview_is_role_scoped():
    customer = _make_user(role=UserRole.CUSTOMER)

    client = Client()
    client.force_login(customer)
    response = client.get(reverse("account-student-overview"))

    assert response.status_code == 403


def test_account_customer_endpoints_return_only_owned_scope():
    customer = _make_user(role=UserRole.CUSTOMER)
    other_customer = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    epp = _make_epp()
    own_project = _make_project(customer, epp, status=ProjectStatus.PUBLISHED)
    _make_project(other_customer, epp, status=ProjectStatus.PUBLISHED)
    _make_application(own_project, student)

    client = Client()
    client.force_login(customer)
    projects_response = client.get(reverse("account-customer-projects"))
    applications_response = client.get(reverse("account-customer-applications"))

    assert projects_response.status_code == 200
    assert len(projects_response.json()) == 1
    assert projects_response.json()[0]["epp_title"] == "Imported EPP"
    assert applications_response.status_code == 200
    assert len(applications_response.json()) == 1
    assert applications_response.json()[0]["project"]["pk"] == own_project.pk


def test_account_cpprp_endpoints_return_moderation_queue_and_application_totals():
    cpprp = _make_user(role=UserRole.CPPRP)
    customer = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    epp = _make_epp()
    project = _make_project(customer, epp, status=ProjectStatus.ON_MODERATION)
    _make_application(project, student, status=ApplicationStatus.SUBMITTED)

    client = Client()
    client.force_login(cpprp)
    queue_response = client.get(reverse("account-cpprp-moderation-queue"))
    applications_response = client.get(reverse("account-cpprp-applications"))

    assert queue_response.status_code == 200
    queue_payload = queue_response.json()
    assert any(item["pk"] == project.pk for item in queue_payload)
    matching = next(item for item in queue_payload if item["pk"] == project.pk)
    assert matching["source_status_raw"] == "Опубликована"
    assert applications_response.status_code == 200
    assert applications_response.json()["totals"][ApplicationStatus.SUBMITTED] >= 1


def test_student_overview_includes_favorites_deadlines_and_templates():
    student = _make_user(role=UserRole.STUDENT)
    project = Project.objects.create(
        title="Recommended systems",
        status=ProjectStatus.PUBLISHED,
        source_type=ProjectSourceType.MANUAL,
    )
    student.profile.favorite_project_ids = [project.pk]
    student.profile.save(update_fields=["favorite_project_ids", "updated_at"])
    suffix = uuid4().hex[:8]
    PlatformDeadline.objects.create(
        slug=f"student-window-{suffix}",
        title="Student window",
        audience=DeadlineAudience.STUDENT,
    )
    DocumentTemplate.objects.create(
        slug=f"student-template-{suffix}",
        title="Student template",
        audience=DeadlineAudience.STUDENT,
        url="https://example.com/doc",
    )

    client = Client()
    client.force_login(student)
    response = client.get(reverse("account-student-overview"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["favorite_projects"][0]["pk"] == project.pk
    assert any(item["slug"] == f"student-window-{suffix}" for item in payload["deadlines"])
    assert any(item["slug"] == f"student-template-{suffix}" for item in payload["templates"])


def test_cpprp_can_create_deadlines_and_export_projects():
    cpprp = _make_user(role=UserRole.CPPRP)
    suffix = uuid4().hex[:8]
    client = Client()
    client.force_login(cpprp)

    deadline_response = client.post(
        reverse("account-cpprp-deadlines"),
        data={
            "slug": f"global-deadline-{suffix}",
            "title": "Global deadline",
            "audience": DeadlineAudience.GLOBAL,
            "description": "Important date",
        },
        content_type="application/json",
    )
    export_response = client.get(reverse("account-cpprp-export-projects"))

    assert deadline_response.status_code == 201
    assert export_response.status_code == 200
    assert "project_id" in export_response.content.decode("utf-8")
