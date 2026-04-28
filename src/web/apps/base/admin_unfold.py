"""Admin compatibility helpers for django-unfold.

The project declares django-unfold as a runtime dependency.  The fallback keeps
local management commands usable in offline environments where the dependency
has not been synced yet; deployed environments with the dependency installed use
Unfold's ModelAdmin automatically.
"""

from importlib import import_module
from typing import Any, cast

from django.contrib import admin

try:  # pragma: no cover - exercised when django-unfold is installed in CI/deploy.
    UnfoldModelAdmin = cast(Any, import_module("unfold.admin").ModelAdmin)
except ModuleNotFoundError:  # pragma: no cover - local offline fallback only.
    UnfoldModelAdmin = cast(Any, admin.ModelAdmin)
