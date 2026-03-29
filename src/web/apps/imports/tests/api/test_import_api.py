from uuid import uuid4

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


def _make_cpprp():
    user = get_user_model().objects.create_user(
        username=f"cpprp-import-{uuid4().hex[:8]}",
        password="placeholder",
    )
    UserProfile.objects.create(user=user, role=UserRole.CPPRP)
    return user


def _make_student():
    user = get_user_model().objects.create_user(
        username=f"student-import-{uuid4().hex[:8]}",
        password="placeholder",
    )
    UserProfile.objects.create(user=user, role=UserRole.STUDENT)
    return user


def test_cpprp_can_trigger_import_and_receive_stats(tmp_path):
    path = tmp_path / "EPP.xlsx"
    payload = _sample_mapping()
    _build_xlsx(path, [EXPECTED_HEADERS, _row_from_mapping(payload)])

    client = Client()
    client.force_login(_make_cpprp())
    with path.open("rb") as fp:
        response = client.post(reverse("api-v1-import-epp"), data={"file": fp})

    assert response.status_code == 201
    assert response.json()["status"] == "completed"
    stats = response.json()["stats"]
    assert stats["projects_created"] + stats["projects_updated"] >= 1


def test_student_cannot_list_import_runs():
    client = Client()
    client.force_login(_make_student())

    response = client.get(reverse("api-v1-import-epp"))

    assert response.status_code == 403
