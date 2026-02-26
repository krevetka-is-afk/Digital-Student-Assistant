import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

# `base.py` lives in `web/config.settings/`, so BASE_DIR is four levels up.
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.getenv(name)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


def database_from_env(default_sqlite_name: str = "db.sqlite3") -> dict[str, dict[str, object]]:
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / default_sqlite_name,
            }
        }

    parsed = urlparse(raw_url)
    scheme = parsed.scheme.lower()

    if scheme == "sqlite":
        path = unquote(parsed.path or "")
        if path.startswith("/"):
            path = path[1:]
        name = Path(path) if path else (BASE_DIR / default_sqlite_name)
        if not name.is_absolute():
            name = BASE_DIR / name
        return {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": name}}

    if scheme in {"postgres", "postgresql", "postgresql+psycopg2"}:
        return {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": unquote((parsed.path or "/").lstrip("/")),
                "USER": unquote(parsed.username or ""),
                "PASSWORD": unquote(parsed.password or ""),
                "HOST": parsed.hostname or "",
                "PORT": str(parsed.port or ""),
            }
        }

    raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme!r}")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party api services
    "debug_toolbar",
    "algoliasearch_django",
    # third party packages
    "rest_framework",
    "rest_framework.authtoken",
    # internal apps
    "apps.base",
    "apps.products",
    "apps.search",
    # healthchecks
    "health_check",  # core
    # "health_check.urls",
    # "health_check.db",  # database check
    # "health_check.cache",  # cache check
    # "health_check.storage",  # storage check
    # "health_check.contrib.celery",  # celery check (optional)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

INTERNAL_IPS = [
    "127.0.0.1",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASES = database_from_env()


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "base.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 10,
}

ALGOLIA = {
    "APPLICATION_ID": os.getenv("ALGOLIA_APPLICATION_ID", ""),
    "API_KEY": os.getenv("ALGOLIA_API_KEY", ""),
    "INDEX_PREFIX": os.getenv("ALGOLIA_INDEX_PREFIX", "SERJ"),
}
