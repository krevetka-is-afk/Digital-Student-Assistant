from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from apps.projects.importers import EXPECTED_HEADERS, import_epp_xlsx
from apps.projects.models import EPP, Project, ProjectSourceType, ProjectStatus
from apps.projects.tests.helpers import _build_xlsx, _row_from_mapping, _sample_mapping
from apps.projects.transitions import normalize_source_status
from django.contrib.auth import get_user_model


def test_import_epp_xlsx_creates_epp_and_project():
    epp_ref = f"10001-{uuid4().hex[:8]}"
    with TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "EPP.xlsx"
        _build_xlsx(
            path,
            [EXPECTED_HEADERS, _row_from_mapping(_sample_mapping(**{"Номер ЭПП": epp_ref}))],
        )

        stats = import_epp_xlsx(path)

    assert stats.epp_created == 1
    assert stats.projects_created == 1
    epp = EPP.objects.get(source_ref=epp_ref)
    project = Project.objects.get(source_type=ProjectSourceType.EPP, epp=epp)
    assert project.epp_id == epp.id
    assert project.status == ProjectStatus.PUBLISHED
    assert project.status_raw == "Опубликована"
    assert project.raw_payload["Наименование вакансии"] == "ML analyst"
    assert project.tech_tags == ["pandas", "numpy", "classification", "Python", "SQL", "ml", "data"]


def test_normalize_source_status_covers_all_current_values():
    assert normalize_source_status("Создана") == ProjectStatus.CREATED
    assert normalize_source_status("Черновик") == ProjectStatus.DRAFT
    assert normalize_source_status("Доработка инициатором") == ProjectStatus.REVISION_REQUESTED
    assert normalize_source_status("Рассмотрение руководителем") == ProjectStatus.SUPERVISOR_REVIEW
    assert normalize_source_status("Опубликована") == ProjectStatus.PUBLISHED
    assert normalize_source_status("Завершена") == ProjectStatus.COMPLETED
    assert normalize_source_status("Отменена") == ProjectStatus.CANCELLED


def test_import_epp_xlsx_is_idempotent_and_updates_existing_records():
    epp_ref = f"10002-{uuid4().hex[:8]}"
    with TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "EPP.xlsx"
        initial = _sample_mapping(**{"Номер ЭПП": epp_ref})
        _build_xlsx(path, [EXPECTED_HEADERS, _row_from_mapping(initial)])
        import_epp_xlsx(path)

        updated = _sample_mapping(**{"Номер ЭПП": epp_ref, "Критерии отбора": "Python, SQL"})
        _build_xlsx(path, [EXPECTED_HEADERS, _row_from_mapping(updated)])
        stats = import_epp_xlsx(path)

    assert stats.projects_updated == 1
    assert (
        Project.objects.filter(source_type=ProjectSourceType.EPP, epp__source_ref=epp_ref).count()
        == 1
    )
    project = Project.objects.get(source_type=ProjectSourceType.EPP, epp__source_ref=epp_ref)
    assert project.selection_criteria == "Python, SQL"


def test_import_epp_xlsx_preserves_local_locked_status():
    epp_ref = f"10003-{uuid4().hex[:8]}"
    with TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "EPP.xlsx"
        _build_xlsx(
            path,
            [EXPECTED_HEADERS, _row_from_mapping(_sample_mapping(**{"Номер ЭПП": epp_ref}))],
        )
        import_epp_xlsx(path)

        project = Project.objects.get(source_type=ProjectSourceType.EPP, epp__source_ref=epp_ref)
        project.status = ProjectStatus.ON_MODERATION
        project.save(update_fields=["status", "updated_at"])

        updated = _sample_mapping(**{"Номер ЭПП": epp_ref, "Статус вакансии/темы": "Завершена"})
        _build_xlsx(path, [EXPECTED_HEADERS, _row_from_mapping(updated)])
        stats = import_epp_xlsx(path)

    project.refresh_from_db()
    assert stats.warnings == 1
    assert project.status == ProjectStatus.ON_MODERATION
    assert project.status_raw == "Завершена"


def test_project_source_constraint_skips_blank_manual_source_ref():
    user = get_user_model().objects.create_user(
        username=f"manual-owner-{uuid4().hex[:8]}",
        password="placeholder",
    )
    first = Project.objects.create(title="Manual one", owner=user)
    second = Project.objects.create(title="Manual two", owner=user)

    assert first.source_ref == ""
    assert second.source_ref == ""
    assert Project.objects.filter(source_type=ProjectSourceType.MANUAL).count() >= 2
