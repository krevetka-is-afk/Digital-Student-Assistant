from uuid import uuid4

from apps.imports.admin import ImportRunAdmin
from apps.imports.models import ImportRun
from apps.projects.tests.helpers import (
    EXPECTED_HEADERS,
    _build_xlsx,
    _row_from_mapping,
    _sample_mapping,
)
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse


def _make_staff_user():
    return get_user_model().objects.create_user(
        username=f"staff-import-admin-{uuid4().hex[:8]}",
        password="placeholder",
        is_staff=True,
        is_superuser=True,
    )


def test_import_run_registered_in_admin():
    assert ImportRun in admin.site._registry
    assert isinstance(admin.site._registry[ImportRun], ImportRunAdmin)


def test_epp_upload_admin_page_renders_file_picker():
    client = Client()
    client.force_login(_make_staff_user())

    response = client.get(reverse("admin:imports_importrun_epp_upload"))

    assert response.status_code == 200
    assert b'Drop epp.xlsx here' in response.content
    assert b'type="file"' in response.content
    assert b'accept=".xlsx' in response.content


def test_staff_can_upload_epp_xlsx_from_admin(tmp_path):
    source_name = f"epp-{uuid4().hex[:8]}.xlsx"
    xlsx_path = tmp_path / source_name
    payload = _sample_mapping()
    _build_xlsx(xlsx_path, [EXPECTED_HEADERS, _row_from_mapping(payload)])

    client = Client()
    staff_user = _make_staff_user()
    client.force_login(staff_user)

    with xlsx_path.open("rb") as fp:
        response = client.post(
            reverse("admin:imports_importrun_epp_upload"),
            data={"file": fp},
        )

    assert response.status_code == 302
    assert response.url == reverse("admin:imports_importrun_changelist")

    import_run = ImportRun.objects.get(source_name=source_name)
    assert import_run.status == "completed"
    assert import_run.imported_by_id == staff_user.id
    assert import_run.stats["projects_created"] + import_run.stats["projects_updated"] >= 1


def test_admin_upload_rejects_non_xlsx_file():
    client = Client()
    client.force_login(_make_staff_user())
    runs_before = ImportRun.objects.count()

    response = client.post(
        reverse("admin:imports_importrun_epp_upload"),
        data={"file": SimpleUploadedFile("epp.csv", b"not,xlsx", content_type="text/csv")},
    )

    assert response.status_code == 200
    assert b"Upload an .xlsx file." in response.content
    assert ImportRun.objects.count() == runs_before
