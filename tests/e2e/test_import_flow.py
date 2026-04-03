from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from apps.applications.models import Application, ApplicationStatus
from apps.outbox.models import OutboxEvent
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from apps.projects.tests.helpers import (
    EXPECTED_HEADERS,
    _build_xlsx,
    _row_from_mapping,
    _sample_mapping,
)
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone


def _make_user(*, role: str | None = None, is_staff: bool = False):
    username = f"e2e-{uuid4().hex[:8]}"
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
@pytest.mark.release_gate("RG-E2E-IMPORT-MODERATION-PUBLISH-APPLY-REVIEW-EXPORT")
@pytest.mark.bpmn(
    "Activity_1sqznqd",
    "Activity_1n2dtih",
    "Activity_0ulodps",
    "Activity_1hv82yj",
    "Activity_174db7k",
)
def test_import_moderation_publish_apply_review_export_flow(tmp_path: Path):
    """
    BPMN: moderation/publish/apply/review path with catalog visibility.
    Release gate: import -> moderation -> publish -> apply -> review -> export.
    """
    cpprp = _make_user(role=UserRole.CPPRP)
    staff = _make_user(is_staff=True)
    student = _make_user(role=UserRole.STUDENT)

    cpprp_client = Client()
    cpprp_client.force_login(cpprp)

    staff_client = Client()
    staff_client.force_login(staff)

    student_client = Client()
    student_client.force_login(student)

    baseline_event_id = (
        OutboxEvent.objects.order_by("-id").values_list("id", flat=True).first() or 0
    )

    suffix = uuid4().hex[:8]
    vacancy_title = f"E2E import project {suffix}"
    today = timezone.localdate()
    payload = _sample_mapping(
        **{
            "Номер ЭПП": f"epp-{suffix}",
            "Наименование вакансии": vacancy_title,
            "Статус вакансии/темы": "Черновик",
            "Дата старта подачи заявок": (today - timedelta(days=1)).isoformat(),
            "Дата окончания подачи заявок": (today + timedelta(days=7)).isoformat(),
            "Количество мест для подачи заявок": "1",
            "Теги вакансии": "python, e2e",
        }
    )
    xlsx_path = tmp_path / "import.xlsx"
    _build_xlsx(xlsx_path, [EXPECTED_HEADERS, _row_from_mapping(payload)])

    with xlsx_path.open("rb") as fp:
        import_response = cpprp_client.post(reverse("api-v1-import-epp"), data={"file": fp})

    assert import_response.status_code == 201
    assert import_response.json()["status"] == "completed"

    project = Project.objects.get(
        source_type=ProjectSourceType.EPP,
        vacancy_title=vacancy_title,
    )
    assert project.status == ProjectStatus.DRAFT

    submit_response = staff_client.post(
        reverse("api-v1-project-submit", kwargs={"pk": project.pk}),
        content_type="application/json",
    )
    assert submit_response.status_code == 200
    assert submit_response.json()["status"] == ProjectStatus.ON_MODERATION

    moderate_response = cpprp_client.post(
        reverse("api-v1-project-moderate", kwargs={"pk": project.pk}),
        data={"decision": "approve"},
        content_type="application/json",
    )
    assert moderate_response.status_code == 200
    assert moderate_response.json()["status"] == ProjectStatus.PUBLISHED

    apply_response = student_client.post(
        reverse("application-list"),
        data={"project": project.pk, "motivation": "I can deliver quickly."},
        content_type="application/json",
    )
    assert apply_response.status_code == 201
    application_id = apply_response.json()["id"]

    review_response = staff_client.post(
        reverse("application-review", kwargs={"pk": application_id}),
        data={"decision": "accept"},
        content_type="application/json",
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == ApplicationStatus.ACCEPTED

    project.refresh_from_db()
    assert project.status == ProjectStatus.STAFFED
    assert project.accepted_participants_count == 1

    project_export_response = cpprp_client.get(reverse("account-cpprp-export-projects"))
    application_export_response = cpprp_client.get(reverse("account-cpprp-export-applications"))
    assert project_export_response.status_code == 200
    assert application_export_response.status_code == 200
    assert str(project.pk) in project_export_response.content.decode("utf-8")
    assert str(application_id) in application_export_response.content.decode("utf-8")

    application = Application.objects.get(pk=application_id)
    assert application.status == ApplicationStatus.ACCEPTED

    new_event_types = set(
        OutboxEvent.objects.filter(id__gt=baseline_event_id).values_list("event_type", flat=True)
    )
    assert {"import.completed", "project.changed", "application.changed"}.issubset(new_event_types)
