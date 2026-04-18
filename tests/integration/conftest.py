import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import django
import pytest
from django.apps import apps as django_apps
from django.conf import settings
from django.core.management import call_command

ROOT_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT_DIR / "src" / "web"
APPS_DIR = WEB_DIR / "apps"
GRAPH_DIR = ROOT_DIR / "src" / "graph"
SAFE_TEST_HOSTS = {"localhost", "127.0.0.1", "postgres"}

for path in (WEB_DIR, APPS_DIR, GRAPH_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _ensure_safe_database_url() -> None:
    def _is_safe_test_url(raw_url: str) -> bool:
        parsed = urlparse(raw_url)
        scheme = parsed.scheme.lower()
        if scheme == "sqlite":
            return "pytest" in parsed.path.lower() or "test" in parsed.path.lower()
        if scheme in {"postgres", "postgresql", "postgresql+psycopg2"}:
            host = (parsed.hostname or "").lower()
            database_name = (parsed.path or "").lstrip("/").lower()
            return host in SAFE_TEST_HOSTS and "test" in database_name
        return False

    explicit_test_db_url = os.getenv("TEST_DB_URL", "").strip()
    if explicit_test_db_url:
        if not _is_safe_test_url(explicit_test_db_url):
            raise RuntimeError(
                "Unsafe TEST_DB_URL. Allowed only test-marked sqlite paths or "
                "PostgreSQL on localhost/127.0.0.1/postgres with database name containing 'test'."
            )
        os.environ["DATABASE_URL"] = explicit_test_db_url
        return

    current_database_url = os.getenv("DATABASE_URL", "").strip()
    if _is_safe_test_url(current_database_url):
        return

    raise RuntimeError(
        "Unsafe DATABASE_URL for destructive integration fixtures. "
        "Set TEST_DB_URL to an isolated test database."
    )


_ensure_safe_database_url()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
if not django_apps.ready:
    django.setup()

if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append("testserver")


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_database():
    if os.environ.get("DSA_TEST_DB_MIGRATED") == "1":
        return
    call_command("migrate", interactive=False, run_syncdb=True, verbosity=0)
    os.environ["DSA_TEST_DB_MIGRATED"] = "1"


@pytest.fixture(autouse=True)
def _isolate_database_state():
    call_command("flush", interactive=False, verbosity=0, allow_cascade=True)
