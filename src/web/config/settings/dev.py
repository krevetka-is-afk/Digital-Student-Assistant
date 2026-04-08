import os
from importlib.util import find_spec

from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = "django-insecure-dev-only-key"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".localhost"]
INTERNAL_IPS = ["127.0.0.1"]

SLOW_QUERY_THRESHOLD_MS = float(os.getenv("DJANGO_SLOW_QUERY_MS", "150"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "slow_queries": {
            "()": "apps.base.logging.SlowQueryFilter",
            "threshold_ms": SLOW_QUERY_THRESHOLD_MS,
        }
    },
    "formatters": {
        "slow_query": {
            "format": "slow-sql duration=%(duration).3fs sql=%(sql)s params=%(params)s",
        }
    },
    "handlers": {
        "console_slow_queries": {
            "class": "logging.StreamHandler",
            "filters": ["slow_queries"],
            "formatter": "slow_query",
        }
    },
    "loggers": {
        "django.db.backends": {
            "handlers": ["console_slow_queries"],
            "level": "DEBUG",
            "propagate": False,
        }
    },
}

if find_spec("debug_toolbar") is not None:
    from debug_toolbar.settings import PANELS_DEFAULTS

    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405
    DEBUG_TOOLBAR_PANELS = [
        p for p in PANELS_DEFAULTS if p != "debug_toolbar.panels.redirects.RedirectsPanel"
    ]
