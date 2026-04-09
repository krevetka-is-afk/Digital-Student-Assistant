from uuid import uuid4

from apps.account.models import DeadlineAudience, DocumentTemplate, PlatformDeadline
from apps.applications.models import Application, ApplicationStatus
from apps.projects.models import EPP, Project, ProjectSourceType, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse


def _make_user(*, role: str, is_staff: bool = False):
    username = f"user-{uuid4().hex[:8]}"
    user = get_user_model().objects.create_user(
        username=username,
        password="placeholder",
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
    assert projects_response.json()["count"] == 1
    assert projects_response.json()["results"][0]["epp_title"] == "Imported EPP"
    assert applications_response.status_code == 200
    assert applications_response.json()["count"] == 1
    assert applications_response.json()["results"][0]["project"]["pk"] == own_project.pk


def test_account_customer_projects_expose_counts_and_states_consistently():
    customer = _make_user(role=UserRole.CUSTOMER)
    submitted_student = _make_user(role=UserRole.STUDENT)
    accepted_student = _make_user(role=UserRole.STUDENT)
    epp = _make_epp()
    project = Project.objects.create(
        title=f"Project {uuid4().hex[:8]}",
        owner=customer,
        epp=epp,
        source_type=ProjectSourceType.EPP,
        source_ref=uuid4().hex,
        status=ProjectStatus.PUBLISHED,
        team_size=2,
    )
    _make_application(project, submitted_student, status=ApplicationStatus.SUBMITTED)
    _make_application(project, accepted_student, status=ApplicationStatus.ACCEPTED)
    project.accepted_participants_count = 1
    project.save(update_fields=["accepted_participants_count", "updated_at"])

    client = Client()
    client.force_login(customer)
    response = client.get(reverse("account-customer-projects"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    item = payload["results"][0]
    assert item["applications_count"] == 2
    assert item["submitted_applications_count"] == 1
    assert item["staffing_state"] == "open"
    assert item["application_window_state"] == "open"


def test_account_customer_applications_support_status_filter():
    customer = _make_user(role=UserRole.CUSTOMER)
    student_a = _make_user(role=UserRole.STUDENT)
    student_b = _make_user(role=UserRole.STUDENT)
    epp = _make_epp()
    project = _make_project(customer, epp, status=ProjectStatus.PUBLISHED)
    _make_application(project, student_a, status=ApplicationStatus.SUBMITTED)
    _make_application(project, student_b, status=ApplicationStatus.ACCEPTED)

    client = Client()
    client.force_login(customer)
    response = client.get(
        reverse("account-customer-applications"), data={"status": ApplicationStatus.ACCEPTED}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["status"] == ApplicationStatus.ACCEPTED


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
    assert any(item["pk"] == project.pk for item in queue_payload["results"])
    matching = next(item for item in queue_payload["results"] if item["pk"] == project.pk)
    assert matching["source_status_raw"] == "Опубликована"
    assert applications_response.status_code == 200
    assert applications_response.json()["totals"][ApplicationStatus.SUBMITTED] >= 1
    assert any(
        item["project"]["pk"] == project.pk
        for item in applications_response.json()["recent"]["results"]
    )


def test_account_customer_applications_is_query_efficient():
    customer = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    epp = _make_epp()
    for _ in range(6):
        project = _make_project(customer, epp, status=ProjectStatus.PUBLISHED)
        _make_application(project, student)

    client = Client()
    client.force_login(customer)
    with CaptureQueriesContext(connection) as query_context:
        response = client.get(reverse("account-customer-applications"), data={"page_size": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 6
    assert len(payload["results"]) == 5
    assert len(query_context.captured_queries) <= 6


def test_account_cpprp_applications_recent_is_paginated_and_query_efficient():
    cpprp = _make_user(role=UserRole.CPPRP)
    customer = _make_user(role=UserRole.CUSTOMER)
    student = _make_user(role=UserRole.STUDENT)
    epp = _make_epp()
    submitted_before = Application.objects.filter(status=ApplicationStatus.SUBMITTED).count()
    accepted_before = Application.objects.filter(status=ApplicationStatus.ACCEPTED).count()
    created_application_ids = []
    for index in range(7):
        project = _make_project(customer, epp, status=ProjectStatus.ON_MODERATION)
        application = _make_application(
            project,
            student,
            status=ApplicationStatus.SUBMITTED if index % 2 == 0 else ApplicationStatus.ACCEPTED,
        )
        created_application_ids.append(application.pk)

    client = Client()
    client.force_login(cpprp)
    with CaptureQueriesContext(connection) as query_context:
        response = client.get(reverse("account-cpprp-applications"), data={"page_size": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"][ApplicationStatus.SUBMITTED] == submitted_before + 4
    assert payload["totals"][ApplicationStatus.ACCEPTED] == accepted_before + 3
    assert payload["recent"]["count"] >= 7
    assert len(payload["recent"]["results"]) == 5
    returned_application_ids = {item["id"] for item in payload["recent"]["results"]}
    assert returned_application_ids.issubset(set(created_application_ids))
    assert len(query_context.captured_queries) <= 9


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


def test_template_download_flow_is_role_scoped_and_uses_uniform_endpoint():
    student = _make_user(role=UserRole.STUDENT)
    customer = _make_user(role=UserRole.CUSTOMER)
    suffix = uuid4().hex[:8]
    student_template = DocumentTemplate.objects.create(
        slug=f"student-template-download-{suffix}",
        title="Student template",
        audience=DeadlineAudience.STUDENT,
        url="https://example.com/student.docx",
    )
    global_template = DocumentTemplate.objects.create(
        slug=f"global-template-download-{suffix}",
        title="Global template",
        audience=DeadlineAudience.GLOBAL,
        url="https://example.com/global.docx",
    )
    customer_template = DocumentTemplate.objects.create(
        slug=f"customer-template-download-{suffix}",
        title="Customer template",
        audience=DeadlineAudience.CUSTOMER,
        url="https://example.com/customer.docx",
    )

    student_client = Client()
    student_client.force_login(student)
    overview_response = student_client.get(reverse("account-student-overview"))

    assert overview_response.status_code == 200
    templates = overview_response.json()["templates"]
    template_slugs = {item["slug"] for item in templates}
    assert student_template.slug in template_slugs
    assert global_template.slug in template_slugs
    assert customer_template.slug not in template_slugs

    download_url = next(
        item["download_url"] for item in templates if item["slug"] == student_template.slug
    )
    download_response = student_client.get(download_url)
    assert download_response.status_code == 302
    assert download_response["Location"] == student_template.url

    forbidden_download_response = student_client.get(
        reverse("account-template-download", kwargs={"pk": customer_template.pk})
    )
    assert forbidden_download_response.status_code == 404

    customer_client = Client()
    customer_client.force_login(customer)
    allowed_for_customer = customer_client.get(
        reverse("account-template-download", kwargs={"pk": customer_template.pk})
    )
    assert allowed_for_customer.status_code == 302
    assert allowed_for_customer["Location"] == customer_template.url


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


def test_student_cannot_access_cpprp_configuration_endpoints():
    student = _make_user(role=UserRole.STUDENT)
    client = Client()
    client.force_login(student)

    deadlines_response = client.get(reverse("account-cpprp-deadlines"))
    export_response = client.get(reverse("account-cpprp-export-projects"))

    assert deadlines_response.status_code == 403
    assert export_response.status_code == 403
