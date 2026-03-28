import os

from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = "django-insecure-dev-only-key"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".localhost"]

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
