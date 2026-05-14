import os
import sys
from pathlib import Path

# Ensure Django apps are importable. The shared suite bootstraps Django in
# apps/conftest.py; this file only extends sys.path for imports under frontend tests.
WEB_DIR = Path(__file__).resolve().parents[3]
APPS_DIR = WEB_DIR / "apps"

for path in (WEB_DIR, APPS_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# "testserver" must be in ALLOWED_HOSTS so django.test.Client requests are
# accepted. Append lazily after django.setup() when this conftest runs before
# apps/conftest.py in some collection orders.
try:
    import django  # noqa: E402

    django.setup()
    from django.conf import settings  # noqa: E402

    if "testserver" not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append("testserver")
except Exception:
    pass
