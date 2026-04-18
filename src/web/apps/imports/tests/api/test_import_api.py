from types import SimpleNamespace
from uuid import uuid4

from apps.imports import views as import_views
from apps.projects.tests.helpers import (
    EXPECTED_HEADERS,
    _build_xlsx,
    _row_from_mapping,
    _sample_mapping,
)
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
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


def test_import_uses_safe_temp_suffix_and_sanitized_source_name(tmp_path, monkeypatch):
    path = tmp_path / "EPP.xlsx"
    payload = _sample_mapping()
    _build_xlsx(path, [EXPECTED_HEADERS, _row_from_mapping(payload)])

    observed_suffixes: list[str] = []

    def _fake_import(import_path):
        observed_suffixes.append(import_path.suffix)
        return SimpleNamespace(
            epp_created=0,
            epp_updated=0,
            projects_created=1,
            projects_updated=0,
            skipped=0,
            errors=0,
            warnings=0,
        )

    monkeypatch.setattr(import_views, "import_epp_xlsx", _fake_import)

    upload = SimpleUploadedFile(
        "../../nested/unsafe-name.xlsm",
        path.read_bytes(),
        content_type="application/vnd.ms-excel.sheet.macroEnabled.12",
    )

    client = Client()
    client.force_login(_make_cpprp())
    response = client.post(reverse("api-v1-import-epp"), data={"file": upload})

    assert response.status_code == 201
    assert observed_suffixes == [".xlsx"]
    assert response.json()["source_name"] == "unsafe-name.xlsm"


def test_student_cannot_list_import_runs():
    client = Client()
    client.force_login(_make_student())

    response = client.get(reverse("api-v1-import-epp"))

    assert response.status_code == 403
