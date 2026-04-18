import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zipfile import BadZipFile

from apps.projects.importers import default_epp_xlsx_path, import_epp_xlsx
from apps.projects.models import EPP, Project
from django.core.management.base import BaseCommand, CommandError


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def bootstrap_state_path() -> Path:
    raw_path = os.getenv("DSA_BOOTSTRAP_STATE_FILE", "/tmp/dsa-bootstrap-state.json")
    return Path(raw_path).expanduser().resolve()


def read_bootstrap_state(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "", ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "failed", f"Bootstrap state file is unreadable or corrupted: {path}"

    status = str(payload.get("status", "")).strip().lower()
    message = str(payload.get("message", "")).strip()
    return status, message


def write_bootstrap_state(path: Path, status: str, message: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


class Command(BaseCommand):
    help = "Import EPP XLSX only when database is empty (bootstrap mode)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="",
            help=(
                "Path to XLSX file. "
                "If omitted, DSA_BOOTSTRAP_XLSX_PATH is used, "
                "then default docs/data_source/EPP.xlsx."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run import even when Project/EPP tables are not empty.",
        )
        parser.add_argument(
            "--strict-missing",
            action="store_true",
            help="Fail when XLSX file is missing (overrides allow-missing behavior).",
        )

    def handle(self, *args, **options):
        enabled = env_bool("DSA_BOOTSTRAP_IMPORT_IF_EMPTY", False)
        if not enabled:
            self.stdout.write("Bootstrap import is disabled (DSA_BOOTSTRAP_IMPORT_IF_EMPTY=false).")
            return

        force = bool(options.get("force"))
        state_file = bootstrap_state_path()
        state_status, state_message = read_bootstrap_state(state_file)
        if state_status == "failed" and not force:
            hint = (
                "Previous bootstrap attempt failed."
                " Fix data/source and rerun with --force to retry bootstrap."
            )
            if state_message:
                hint = f"{hint} Last error: {state_message}"
            raise CommandError(hint)

        if not force and (Project.objects.exists() or EPP.objects.exists()):
            self.stdout.write("Bootstrap import skipped: database already contains data.")
            return

        env_path = os.getenv("DSA_BOOTSTRAP_XLSX_PATH", "").strip()
        raw_path = options.get("path") or env_path or str(default_epp_xlsx_path())
        path = Path(raw_path).expanduser().resolve()

        allow_missing = env_bool("DSA_BOOTSTRAP_ALLOW_MISSING_XLSX", True)
        fail_on_import_errors = env_bool("DSA_BOOTSTRAP_FAIL_ON_IMPORT_ERRORS", True)
        if options.get("strict_missing"):
            allow_missing = False

        if not path.exists():
            message = f"Bootstrap XLSX was not found: {path}"
            if allow_missing:
                write_bootstrap_state(state_file, "skipped", message)
                self.stdout.write(f"{message}. Skipping.")
                return
            write_bootstrap_state(state_file, "failed", message)
            raise CommandError(message)

        write_bootstrap_state(state_file, "in_progress", f"Import started for {path}")
        try:
            stats = import_epp_xlsx(path)
        except (BadZipFile, OSError, ValueError) as exc:
            if allow_missing:
                write_bootstrap_state(state_file, "skipped", str(exc))
                self.stdout.write(f"Bootstrap import skipped: {exc}")
                return
            write_bootstrap_state(state_file, "failed", str(exc))
            raise CommandError(str(exc)) from exc

        if fail_on_import_errors and stats.errors > 0:
            write_bootstrap_state(
                state_file,
                "failed",
                f"row_level_errors={stats.errors}",
            )
            raise CommandError(
                "Bootstrap import completed with row-level errors "
                f"(errors={stats.errors}). "
                "Refusing to continue because DSA_BOOTSTRAP_FAIL_ON_IMPORT_ERRORS=true."
            )

        if stats.errors > 0:
            write_bootstrap_state(
                state_file,
                "succeeded_with_errors",
                f"row_level_errors={stats.errors}",
            )
        else:
            write_bootstrap_state(
                state_file,
                "succeeded",
                "Bootstrap import completed successfully.",
            )

        self.stdout.write(
            "Bootstrap EPP import completed: "
            f"epp_created={stats.epp_created}, "
            f"epp_updated={stats.epp_updated}, "
            f"projects_created={stats.projects_created}, "
            f"projects_updated={stats.projects_updated}, "
            f"skipped={stats.skipped}, "
            f"errors={stats.errors}, "
            f"warnings={stats.warnings}"
        )
