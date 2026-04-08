from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
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
