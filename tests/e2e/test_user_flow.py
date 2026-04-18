from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from apps.account.models import DeadlineAudience, DocumentTemplate, PlatformDeadline
from apps.applications.models import ApplicationStatus
from apps.outbox.models import OutboxEvent
from apps.projects.models import ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone


def _make_user(*, role: str | None = None, is_staff: bool = False):
    username = f"user-flow-{uuid4().hex[:8]}"
    user = get_user_model().objects.create_user(
        username=username,
        password="placeholder",
        email=f"{username}@example.com",
        is_staff=is_staff,
    )
    if role is not None:
        UserProfile.objects.create(user=user, role=role)
    return user


@pytest.mark.e2e
@pytest.mark.release_gate("RG-E2E-INITIATIVE-REVISION-CYCLE")
@pytest.mark.bpmn(
    "Gateway_1h5qw46",
    "Event_13v5ehs",
    "Event_1wctsks",
    "Activity_1hv82yj",
    "Activity_084g7qe",
)
def test_initiative_project_reject_revision_publish_and_application_reject_flow():
    """
    BPMN: moderation reject/approve branch and application reject branch.
    Release gate: initiative full lifecycle with revision loop.
    """
    customer = _make_user(role=UserRole.CUSTOMER)
    cpprp = _make_user(role=UserRole.CPPRP)
    student = _make_user(role=UserRole.STUDENT)

    customer_client = Client()
    customer_client.force_login(customer)

    cpprp_client = Client()
    cpprp_client.force_login(cpprp)

    student_client = Client()
    student_client.force_login(student)

    baseline_event_id = (
        OutboxEvent.objects.order_by("-id").values_list("id", flat=True).first() or 0
    )

    suffix = uuid4().hex[:8]
    today = timezone.localdate()
    create_response = customer_client.post(
        reverse("api-v1-project-list"),
        data={
            "title": f"Initiative project {suffix}",
            "description": "Initial project draft.",
            "source_type": "initiative",
            "team_size": 2,
            "application_opened_at": (today - timedelta(days=1)).isoformat(),
            "application_deadline": (today + timedelta(days=10)).isoformat(),
            "tech_tags": ["python", "architecture"],
        },
        content_type="application/json",
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["pk"]
    assert create_response.json()["status"] == ProjectStatus.DRAFT

    submit_first_response = customer_client.post(
        reverse("api-v1-project-submit", kwargs={"pk": project_id}),
        content_type="application/json",
    )
    assert submit_first_response.status_code == 200
    assert submit_first_response.json()["status"] == ProjectStatus.ON_MODERATION

    reject_comment = (
        "Needs clearer scope, concrete deliverables, and measurable outcomes "
        "for each milestone before approval."
    )
    reject_response = cpprp_client.post(
        reverse("api-v1-project-moderate", kwargs={"pk": project_id}),
        data={"decision": "reject", "comment": reject_comment},
        content_type="application/json",
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == ProjectStatus.REVISION_REQUESTED

    update_response = customer_client.patch(
        reverse("api-v1-project-detail", kwargs={"pk": project_id}),
        data={
            "description": "Updated scope with milestones and measurable outcomes.",
            "tech_tags": ["python", "architecture", "mlops"],
        },
        content_type="application/json",
    )
    assert update_response.status_code == 200

    submit_second_response = customer_client.post(
        reverse("api-v1-project-submit", kwargs={"pk": project_id}),
        content_type="application/json",
    )
    assert submit_second_response.status_code == 200
    assert submit_second_response.json()["status"] == ProjectStatus.ON_MODERATION

    approve_response = cpprp_client.post(
        reverse("api-v1-project-moderate", kwargs={"pk": project_id}),
        data={"decision": "approve"},
        content_type="application/json",
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == ProjectStatus.PUBLISHED

    apply_response = student_client.post(
        reverse("application-list"),
        data={"project": project_id, "motivation": "Strong match with my background."},
        content_type="application/json",
    )
    assert apply_response.status_code == 201
    application_id = apply_response.json()["id"]

    review_reject_response = customer_client.post(
        reverse("application-review", kwargs={"pk": application_id}),
        data={
            "decision": "reject",
            "comment": "Thank you for applying, but we need deeper prior backend experience.",
        },
        content_type="application/json",
    )
    assert review_reject_response.status_code == 200
    assert review_reject_response.json()["status"] == ApplicationStatus.REJECTED

    customer_applications_response = customer_client.get(reverse("account-customer-applications"))
    assert customer_applications_response.status_code == 200
    assert (
        customer_applications_response.json()["results"][0]["status"]
        == ApplicationStatus.REJECTED
    )

    new_event_types = list(
        OutboxEvent.objects.filter(id__gt=baseline_event_id)
        .order_by("id")
        .values_list("event_type", flat=True)
    )
    assert "project.changed" in new_event_types
    assert "application.changed" in new_event_types


@pytest.mark.e2e
def test_role_dashboards_states_and_template_download_flow():
    customer = _make_user(role=UserRole.CUSTOMER)
    cpprp = _make_user(role=UserRole.CPPRP)
    student = _make_user(role=UserRole.STUDENT)

    customer_client = Client()
    customer_client.force_login(customer)

    cpprp_client = Client()
    cpprp_client.force_login(cpprp)

    student_client = Client()
    student_client.force_login(student)

    suffix = uuid4().hex[:8]
    PlatformDeadline.objects.create(
        slug=f"student-deadline-{suffix}",
        title="Student deadline",
        audience=DeadlineAudience.STUDENT,
    )
    student_template = DocumentTemplate.objects.create(
        slug=f"student-template-{suffix}",
        title="Student template",
        audience=DeadlineAudience.STUDENT,
        url="https://example.com/student-template.docx",
    )
    customer_template = DocumentTemplate.objects.create(
        slug=f"customer-template-{suffix}",
        title="Customer template",
        audience=DeadlineAudience.CUSTOMER,
        url="https://example.com/customer-template.docx",
    )

    today = timezone.localdate()
    create_response = customer_client.post(
        reverse("api-v1-project-list"),
        data={
            "title": f"Dashboard project {suffix}",
            "description": "Project for dashboard acceptance checks.",
            "source_type": "initiative",
            "team_size": 2,
            "application_opened_at": (today - timedelta(days=1)).isoformat(),
            "application_deadline": (today + timedelta(days=7)).isoformat(),
        },
        content_type="application/json",
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["pk"]

    submit_response = customer_client.post(
        reverse("api-v1-project-submit", kwargs={"pk": project_id}),
        content_type="application/json",
    )
    assert submit_response.status_code == 200
    moderate_response = cpprp_client.post(
        reverse("api-v1-project-moderate", kwargs={"pk": project_id}),
        data={"decision": "approve"},
        content_type="application/json",
    )
    assert moderate_response.status_code == 200
    assert moderate_response.json()["status"] == ProjectStatus.PUBLISHED

    list_response = student_client.get(
        reverse("api-v1-project-list"),
        data={"application_window_state": "open"},
    )
    assert list_response.status_code == 200
    listed_project = next(
        item for item in list_response.json()["results"] if item["pk"] == project_id
    )
    assert listed_project["applications_count"] == 0
    assert listed_project["staffing_state"] == "open"
    assert listed_project["application_window_state"] == "open"

    apply_response = student_client.post(
        reverse("application-list"),
        data={"project": project_id, "motivation": "Ready to contribute."},
        content_type="application/json",
    )
    assert apply_response.status_code == 201
    application_id = apply_response.json()["id"]

    customer_projects_response = customer_client.get(reverse("account-customer-projects"))
    assert customer_projects_response.status_code == 200
    customer_project = next(
        item
        for item in customer_projects_response.json()["results"]
        if item["pk"] == project_id
    )
    assert customer_project["applications_count"] == 1
    assert customer_project["submitted_applications_count"] == 1
    assert customer_project["staffing_state"] == "open"
    assert customer_project["application_window_state"] == "open"

    customer_applications_response = customer_client.get(
        reverse("account-customer-applications"),
        data={"status": ApplicationStatus.SUBMITTED},
    )
    assert customer_applications_response.status_code == 200
    assert any(
        item["id"] == application_id and item["status"] == ApplicationStatus.SUBMITTED
        for item in customer_applications_response.json()["results"]
    )

    cpprp_applications_response = cpprp_client.get(
        reverse("account-cpprp-applications"),
        data={"status": ApplicationStatus.SUBMITTED},
    )
    assert cpprp_applications_response.status_code == 200
    assert cpprp_applications_response.json()["totals"][ApplicationStatus.SUBMITTED] >= 1
    cpprp_recent = cpprp_applications_response.json()["recent"]["results"]
    matched_recent = next(item for item in cpprp_recent if item["id"] == application_id)
    assert matched_recent["project"]["applications_count"] == 1
    assert matched_recent["project"]["application_window_state"] == "open"

    student_overview_response = student_client.get(reverse("account-student-overview"))
    assert student_overview_response.status_code == 200
    overview_payload = student_overview_response.json()
    assert any(
        item["slug"] == f"student-deadline-{suffix}"
        for item in overview_payload["deadlines"]
    )
    overview_template = next(
        item for item in overview_payload["templates"] if item["slug"] == student_template.slug
    )
    assert overview_template["download_url"]
    download_response = student_client.get(overview_template["download_url"])
    assert download_response.status_code == 302
    assert download_response["Location"] == student_template.url

    forbidden_student_template_for_customer = customer_client.get(
        reverse("account-template-download", kwargs={"pk": student_template.pk})
    )
    assert forbidden_student_template_for_customer.status_code == 404
    allowed_customer_template = customer_client.get(
        reverse("account-template-download", kwargs={"pk": customer_template.pk})
    )
    assert allowed_customer_template.status_code == 302
    assert allowed_customer_template["Location"] == customer_template.url
