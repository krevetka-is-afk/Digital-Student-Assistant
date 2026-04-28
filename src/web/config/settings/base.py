import json
import os
from importlib.util import find_spec
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# `base.py` lives in `web/config/settings/`, so BASE_DIR is four levels up.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if os.getenv("DJANGO_LOAD_DOTENV", "").strip().lower() in {"1", "true", "yes", "on"}:
    load_dotenv(BASE_DIR / ".env")
elif not os.getenv("DJANGO_SETTINGS_MODULE", "").endswith(".prod"):
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


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value.strip())


def env_json_map(name: str) -> dict[str, str]:
    value = env_secret(name)
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name} must contain a valid JSON object.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{name} must contain a JSON object.")
    normalized: dict[str, str] = {}
    for key, token in parsed.items():
        key_str = str(key).strip()
        token_str = str(token).strip()
        if key_str and token_str:
            normalized[key_str] = token_str
    return normalized


def env_secret(name: str) -> str | None:
    """Load secret from NAME or from a mounted file via NAME_FILE."""
    file_var = f"{name}_FILE"
    file_path = os.getenv(file_var)
    if file_path:
        try:
            value = Path(file_path).read_text(encoding="utf-8").strip()
            return value or None
        except OSError as exc:
            raise RuntimeError(f"Unable to read secret file configured in {file_var}.") from exc
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def database_from_env(default_sqlite_name: str = "db.sqlite3") -> dict[str, dict[str, object]]:
    raw_url = env_secret("DATABASE_URL")
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


UNFOLD_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
]

if find_spec("unfold") is None:
    UNFOLD_APPS = []


INSTALLED_APPS = [
    *UNFOLD_APPS,
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party packages
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    # internal apps
    "apps.base",
    "apps.account",
    "apps.users",
    "apps.projects",
    "apps.applications",
    "apps.search",
    "apps.imports",
    "apps.outbox",
    "apps.recs",
    "apps.faculty",
    "apps.frontend",
    # healthchecks
    "health_check",  # core
    # "health_check.urls",
    # "health_check.db",  # database check
    # "health_check.cache",  # cache check
    # "health_check.storage",  # storage check
    # "health_check.contrib.celery",  # celery check
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.base.metrics.PrometheusMetricsMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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
STATIC_ROOT = BASE_DIR / "staticfiles"

UNFOLD = {
    "SITE_TITLE": "DSA Admin",
    "SITE_HEADER": "Digital Student Assistant",
    "SITE_SUBHEADER": _("Administration panel"),
    "SITE_SYMBOL": "school",
    "SITE_URL": "/",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "BORDER_RADIUS": "0.5rem",
    "COLORS": {
        "primary": {
            "50": "238 242 255",
            "100": "224 231 255",
            "200": "199 210 254",
            "300": "165 180 252",
            "400": "129 140 248",
            "500": "99 102 241",
            "600": "79 70 229",
            "700": "67 56 202",
            "800": "55 48 163",
            "900": "49 46 129",
            "950": "30 27 75",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": _("Core"),
                "separator": True,
                "items": [
                    {
                        "title": _("Projects"),
                        "icon": "work",
                        "link": reverse_lazy("admin:projects_project_changelist"),
                    },
                    {
                        "title": _("EPP catalog"),
                        "icon": "dataset",
                        "link": reverse_lazy("admin:projects_epp_changelist"),
                    },
                    {
                        "title": _("Upload EPP XLSX"),
                        "icon": "upload_file",
                        "link": reverse_lazy("admin:imports_importrun_epp_upload"),
                    },
                    {
                        "title": _("Import runs"),
                        "icon": "history",
                        "link": reverse_lazy("admin:imports_importrun_changelist"),
                    },
                    {
                        "title": _("Applications"),
                        "icon": "assignment",
                        "link": reverse_lazy("admin:applications_application_changelist"),
                    },
                ],
            },
            {
                "title": _("Users"),
                "separator": True,
                "items": [
                    {
                        "title": _("Django users"),
                        "icon": "person",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                    },
                    {
                        "title": _("Groups"),
                        "icon": "groups",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                    {
                        "title": _("Profiles"),
                        "icon": "badge",
                        "link": reverse_lazy("admin:users_userprofile_changelist"),
                    },
                    {
                        "title": _("Email verification"),
                        "icon": "mark_email_read",
                        "link": reverse_lazy("admin:users_emailverificationcode_changelist"),
                    },
                ],
            },
        ],
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "apps.base.authentication.ServiceTokenAuthentication",
        "apps.base.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "PAGE_SIZE": 10,
}

OUTBOX_SERVICE_TOKENS = env_json_map("OUTBOX_SERVICE_TOKENS")
AUTH_ENABLE_LOCAL_TOKEN_FALLBACK = env_bool("AUTH_ENABLE_LOCAL_TOKEN_FALLBACK", True)
FACULTY_SERVICE_URL = (env_secret("FACULTY_SERVICE_URL") or "").rstrip("/")
FACULTY_SERVICE_TIMEOUT = float(os.getenv("FACULTY_SERVICE_TIMEOUT", "10"))

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
).strip()
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "no-reply@digital-student-assistant.local",
).strip()
EMAIL_HOST = os.getenv("EMAIL_HOST", "").strip()
EMAIL_PORT = env_int("EMAIL_PORT", 25)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = env_secret("EMAIL_HOST_PASSWORD") or ""
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 10)

EMAIL_VERIFICATION_CODE_TTL_SECONDS = env_int("EMAIL_VERIFICATION_CODE_TTL_SECONDS", 900)
EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS = env_int(
    "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS",
    60,
)
EMAIL_VERIFICATION_MAX_ATTEMPTS = env_int("EMAIL_VERIFICATION_MAX_ATTEMPTS", 5)

SPECTACULAR_SETTINGS = {
    "TITLE": "Digital Student Assistant API",
    "DESCRIPTION": "Versioned REST API for web and future service integrations.",
    "VERSION": "1.0.0",
    "PREPROCESSING_HOOKS": [
        "config.schema.public_api_only_preprocessing_hook",
    ],
}
