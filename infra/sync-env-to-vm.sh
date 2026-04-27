#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${ENV_NAME:-prod}"
MODE="${MODE:-push}"
LOCAL_ENV="${LOCAL_ENV:-infra/.env.${ENV_NAME}}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/digital-student-assistant}"
VM_HOST="${VM_HOST:?VM_HOST is required}"
VM_USER="${VM_USER:?VM_USER is required}"
VM_PORT="${VM_PORT:-22}"
SSH_KEY="${SSH_KEY:-}"

if [[ "$ENV_NAME" != "prod" && "$ENV_NAME" != "staging" ]]; then
  echo "ENV_NAME must be prod or staging" >&2
  exit 2
fi

if [[ "$MODE" != "push" && "$MODE" != "pull" ]]; then
  echo "MODE must be push or pull" >&2
  exit 2
fi

if [[ "$MODE" == "push" && ! -f "$LOCAL_ENV" ]]; then
  echo "Local env file not found: $LOCAL_ENV" >&2
  exit 2
fi

validate_env() {
  python3 - "$ENV_NAME" "$LOCAL_ENV" <<'PY'
import sys
from pathlib import Path

env_name, env_path = sys.argv[1], Path(sys.argv[2])
required = {
    "prod": {
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "DJANGO_SECURE_SSL_REDIRECT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
    },
    "staging": {
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "DJANGO_SECURE_SSL_REDIRECT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
        "NEO4J_AUTH",
        "NEO4J_USER",
        "NEO4J_PASSWORD",
        "ML_SERVICE_URL",
    },
}[env_name]

values: dict[str, str] = {}
for raw_line in env_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    values[key] = value.strip()

missing = sorted(key for key in required if not values.get(key))
if missing:
    print("Missing required keys:", ", ".join(missing), file=sys.stderr)
    raise SystemExit(1)

placeholder_markers = ("replace", "change-me", "placeholder", "example.com", "staging.example")
placeholder_keys = sorted(
    key for key, value in values.items() if any(marker in value for marker in placeholder_markers)
)
if placeholder_keys:
    print("Placeholder values remain in:", ", ".join(placeholder_keys), file=sys.stderr)
    raise SystemExit(1)

smtp_required = {"EMAIL_HOST", "EMAIL_PORT", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD"}
if values.get("EMAIL_BACKEND") == "django.core.mail.backends.smtp.EmailBackend":
    missing_smtp = sorted(key for key in smtp_required if not values.get(key))
    if missing_smtp:
        print("SMTP backend is enabled but keys are missing:", ", ".join(missing_smtp), file=sys.stderr)
        raise SystemExit(1)

print(f"{env_path} is valid for {env_name}; values are not printed.")
PY
}

ssh_args=(-p "$VM_PORT")
scp_args=(-P "$VM_PORT")
if [[ -n "$SSH_KEY" ]]; then
  ssh_args+=(-i "$SSH_KEY")
  scp_args+=(-i "$SSH_KEY")
fi

remote_env="infra/.env.${ENV_NAME}"
tmp_name=".env.${ENV_NAME}.tmp.$$"

if [[ "$MODE" == "pull" ]]; then
  mkdir -p "$(dirname "$LOCAL_ENV")"
  scp "${scp_args[@]}" "${VM_USER}@${VM_HOST}:${REMOTE_APP_DIR}/${remote_env}" "$LOCAL_ENV"
  chmod 600 "$LOCAL_ENV"
  echo "Pulled ${VM_USER}@${VM_HOST}:${REMOTE_APP_DIR}/${remote_env} to $LOCAL_ENV"
  exit 0
fi

validate_env
scp "${scp_args[@]}" "$LOCAL_ENV" "${VM_USER}@${VM_HOST}:/tmp/${tmp_name}"
ssh "${ssh_args[@]}" "${VM_USER}@${VM_HOST}" \
  "set -euo pipefail; cd '$REMOTE_APP_DIR'; install -m 600 /tmp/'$tmp_name' '$remote_env'; rm -f /tmp/'$tmp_name'; ls -l '$remote_env'"

echo "Synced $LOCAL_ENV to ${VM_USER}@${VM_HOST}:${REMOTE_APP_DIR}/${remote_env}"
