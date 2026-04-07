import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from apps.projects.importers import EXPECTED_HEADERS, ImportStats
from apps.projects.management.commands import bootstrap_epp_if_empty as command_module
from apps.projects.models import EPP, Project
from apps.projects.tests.helpers import _build_xlsx, _row_from_mapping, _sample_mapping
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.fixture(autouse=True)
def _isolated_bootstrap_state_file(monkeypatch, tmp_path):
    monkeypatch.setenv("DSA_BOOTSTRAP_STATE_FILE", str(tmp_path / "bootstrap-state.json"))


def test_bootstrap_imports_xlsx_when_database_is_empty(monkeypatch):
    epp_ref = f"bootstrap-{uuid4().hex[:8]}"
    with TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "EPP.xlsx"
        _build_xlsx(
            path,
            [EXPECTED_HEADERS, _row_from_mapping(_sample_mapping(**{"Номер ЭПП": epp_ref}))],
        )

        monkeypatch.setattr(Project.objects, "exists", lambda: False)
        monkeypatch.setattr(EPP.objects, "exists", lambda: False)
        monkeypatch.setenv("DSA_BOOTSTRAP_IMPORT_IF_EMPTY", "true")
        monkeypatch.setenv("DSA_BOOTSTRAP_XLSX_PATH", str(path))
        monkeypatch.setenv("DSA_BOOTSTRAP_ALLOW_MISSING_XLSX", "false")

        called_with: list[Path] = []

        def _fake_import(xlsx_path: Path) -> ImportStats:
            called_with.append(xlsx_path)
            return ImportStats()

        monkeypatch.setattr(command_module, "import_epp_xlsx", _fake_import)
        call_command("bootstrap_epp_if_empty")

    assert called_with == [path.resolve()]


def test_bootstrap_skips_when_database_has_data(monkeypatch):
    monkeypatch.setattr(Project.objects, "exists", lambda: True)
    monkeypatch.setattr(EPP.objects, "exists", lambda: False)
    missing = Path("/tmp/non-existing-bootstrap.xlsx")

    monkeypatch.setenv("DSA_BOOTSTRAP_IMPORT_IF_EMPTY", "true")
    monkeypatch.setenv("DSA_BOOTSTRAP_XLSX_PATH", str(missing))
    monkeypatch.setenv("DSA_BOOTSTRAP_ALLOW_MISSING_XLSX", "false")

    def _must_not_be_called(_: Path):
        raise RuntimeError("must skip")

    monkeypatch.setattr(
        command_module,
        "import_epp_xlsx",
        _must_not_be_called,
    )

    call_command("bootstrap_epp_if_empty")


def test_bootstrap_fails_on_missing_xlsx_when_strict(monkeypatch):
    monkeypatch.setattr(Project.objects, "exists", lambda: False)
    monkeypatch.setattr(EPP.objects, "exists", lambda: False)
    missing = Path("/tmp/non-existing-bootstrap-strict.xlsx")
    monkeypatch.setenv("DSA_BOOTSTRAP_IMPORT_IF_EMPTY", "true")
    monkeypatch.setenv("DSA_BOOTSTRAP_XLSX_PATH", str(missing))
    monkeypatch.setenv("DSA_BOOTSTRAP_ALLOW_MISSING_XLSX", "false")

    with pytest.raises(CommandError, match="Bootstrap XLSX was not found"):
        call_command("bootstrap_epp_if_empty")


def test_bootstrap_skips_missing_xlsx_when_allow_missing(monkeypatch):
    monkeypatch.setattr(Project.objects, "exists", lambda: False)
    monkeypatch.setattr(EPP.objects, "exists", lambda: False)
    missing = Path("/tmp/non-existing-bootstrap-optional.xlsx")
    monkeypatch.setenv("DSA_BOOTSTRAP_IMPORT_IF_EMPTY", "true")
    monkeypatch.setenv("DSA_BOOTSTRAP_XLSX_PATH", str(missing))
    monkeypatch.setenv("DSA_BOOTSTRAP_ALLOW_MISSING_XLSX", "true")

    call_command("bootstrap_epp_if_empty")


def test_bootstrap_skips_invalid_xlsx_when_allow_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(Project.objects, "exists", lambda: False)
    monkeypatch.setattr(EPP.objects, "exists", lambda: False)
    invalid = tmp_path / "invalid.xlsx"
    invalid.write_text("not-a-zip")
    monkeypatch.setenv("DSA_BOOTSTRAP_IMPORT_IF_EMPTY", "true")
    monkeypatch.setenv("DSA_BOOTSTRAP_XLSX_PATH", str(invalid))
    monkeypatch.setenv("DSA_BOOTSTRAP_ALLOW_MISSING_XLSX", "true")

    call_command("bootstrap_epp_if_empty")


def test_bootstrap_fails_when_import_reports_row_errors(monkeypatch):
    monkeypatch.setattr(Project.objects, "exists", lambda: False)
    monkeypatch.setattr(EPP.objects, "exists", lambda: False)
    with TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "EPP.xlsx"
        path.write_text("not-an-xlsx")
        monkeypatch.setenv("DSA_BOOTSTRAP_IMPORT_IF_EMPTY", "true")
        monkeypatch.setenv("DSA_BOOTSTRAP_XLSX_PATH", str(path))
        monkeypatch.setenv("DSA_BOOTSTRAP_ALLOW_MISSING_XLSX", "false")
        monkeypatch.setenv("DSA_BOOTSTRAP_FAIL_ON_IMPORT_ERRORS", "true")
        monkeypatch.setattr(command_module, "import_epp_xlsx", lambda _: ImportStats(errors=1))

        with pytest.raises(CommandError, match="completed with row-level errors"):
            call_command("bootstrap_epp_if_empty")


def test_bootstrap_blocks_startup_if_previous_attempt_failed(monkeypatch, tmp_path):
    monkeypatch.setattr(Project.objects, "exists", lambda: True)
    monkeypatch.setattr(EPP.objects, "exists", lambda: True)
    state_path = tmp_path / "bootstrap-state.json"
    state_path.write_text(
        json.dumps({"status": "failed", "message": "row_level_errors=1"}),
        encoding="utf-8",
    )

    monkeypatch.setenv("DSA_BOOTSTRAP_IMPORT_IF_EMPTY", "true")
    monkeypatch.setenv("DSA_BOOTSTRAP_ALLOW_MISSING_XLSX", "true")
    monkeypatch.setenv("DSA_BOOTSTRAP_STATE_FILE", str(state_path))

    with pytest.raises(CommandError, match="Previous bootstrap attempt failed"):
        call_command("bootstrap_epp_if_empty")
