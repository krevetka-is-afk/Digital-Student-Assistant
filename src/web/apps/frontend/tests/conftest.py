import os
import sys
from pathlib import Path

# Ensure Django apps are importable.  pytest-django reads DJANGO_SETTINGS_MODULE
# from pyproject.toml [tool.pytest.ini_options] and calls django.setup() on its
# own; we only need to extend sys.path here so the imports resolve correctly.
WEB_DIR = Path(__file__).resolve().parents[3]
APPS_DIR = WEB_DIR / "apps"

for path in (WEB_DIR, APPS_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

# Keep DJANGO_SETTINGS_MODULE as a fallback for environments where pytest-django
# is not yet installed (e.g. right after a fresh checkout before `uv sync`).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# "testserver" must be in ALLOWED_HOSTS so django.test.Client requests are
# accepted.  Append it lazily so Django is already configured when we touch
# settings (pytest-django may call django.setup() before this conftest loads
# further, but setdefault above ensures the settings module is set first).
try:
    import django  # noqa: E402

    django.setup()
    from django.conf import settings  # noqa: E402

    if "testserver" not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append("testserver")
except Exception:
    pass
