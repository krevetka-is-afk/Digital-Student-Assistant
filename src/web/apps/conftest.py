import os
import sys
from pathlib import Path

import pytest

WEB_DIR = Path(__file__).resolve().parents[1]
APPS_DIR = WEB_DIR / "apps"

for path in (WEB_DIR, APPS_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

try:
    import django

    django.setup()
    from django.conf import settings

    if "testserver" not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append("testserver")
except Exception:
    pass


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()
