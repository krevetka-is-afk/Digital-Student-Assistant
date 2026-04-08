import os
import sys
from pathlib import Path

import django
import pytest
from django.conf import settings
from django.core.management import call_command

WEB_DIR = Path(__file__).resolve().parents[1]
APPS_DIR = WEB_DIR / "apps"

for path in (WEB_DIR, APPS_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append("testserver")


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_database():
    call_command("migrate", interactive=False, run_syncdb=True, verbosity=0)
