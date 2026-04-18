#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/dsa}"
COMPOSE_FILE="${COMPOSE_FILE:-$APP_DIR/infra/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$APP_DIR/infra/.env.prod}"
ENV_EXAMPLE_FILE="${ENV_EXAMPLE_FILE:-$APP_DIR/infra/.env.prod.example}"
PORT_MAPPING="${PORT_MAPPING:-8080:80}"
PUBLIC_HOST="${PUBLIC_HOST:-}"
RUN_SMOKE="${RUN_SMOKE:-1}"
SMOKE_BASE_URL="${SMOKE_BASE_URL:-}"

usage() {
  cat <<'EOF'
Usage: scripts/deploy-prod-vm.sh

Environment variables:
  APP_DIR          Project directory on VM (default: /opt/dsa)
  COMPOSE_FILE     Compose file path (default: $APP_DIR/infra/docker-compose.prod.yml)
  ENV_FILE         Prod env file path (default: $APP_DIR/infra/.env.prod)
  ENV_EXAMPLE_FILE Env template file (default: $APP_DIR/infra/.env.prod.example)
  PORT_MAPPING     Nginx port mapping, host:container (default: 8080:80)
  PUBLIC_HOST      Public host/IP for DJANGO_ALLOWED_HOSTS/CSRF (optional)
  RUN_SMOKE        1 to run smoke-prod.sh, 0 to skip (default: 1)
  SMOKE_BASE_URL   Override smoke base URL (default: http://127.0.0.1:<host_port>)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "APP_DIR does not exist: $APP_DIR" >&2
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_EXAMPLE_FILE" ]]; then
    echo "ENV_FILE is missing and template not found: $ENV_EXAMPLE_FILE" >&2
    exit 1
  fi
  cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

set_env_key() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    printf "%s=%s\n" "$key" "$value" >>"$ENV_FILE"
  fi
}

get_env_val() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true
}

is_placeholder() {
  local value="${1:-}"
  [[ -z "$value" || "$value" =~ ^(replace|change-me|placeholder) ]]
}

replace_if_placeholder() {
  local key="$1"
  local candidate="$2"
  local current
  current="$(get_env_val "$key")"
  if is_placeholder "$current"; then
    set_env_key "$key" "$candidate"
  fi
}

set_default_env_key() {
  local key="$1"
  local value="$2"
  local current
  current="$(get_env_val "$key")"
  if [[ -z "$current" ]]; then
    set_env_key "$key" "$value"
  fi
}

DJ_SECRET="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
)"
PG_PASS="$(openssl rand -hex 20)"
NEO_PASS="$(openssl rand -hex 20)"

replace_if_placeholder "DJANGO_SECRET_KEY" "$DJ_SECRET"
replace_if_placeholder "POSTGRES_PASSWORD" "$PG_PASS"
replace_if_placeholder "NEO4J_PASSWORD" "$NEO_PASS"
POSTGRES_DB_VAL="$(get_env_val POSTGRES_DB)"
POSTGRES_USER_VAL="$(get_env_val POSTGRES_USER)"
POSTGRES_PASS_VAL="$(get_env_val POSTGRES_PASSWORD)"
if [[ -z "$POSTGRES_DB_VAL" ]]; then
  POSTGRES_DB_VAL="dsa"
fi
if [[ -z "$POSTGRES_USER_VAL" ]]; then
  POSTGRES_USER_VAL="dsa"
fi
if is_placeholder "$POSTGRES_PASS_VAL"; then
  POSTGRES_PASS_VAL="$PG_PASS"
  set_env_key "POSTGRES_PASSWORD" "$POSTGRES_PASS_VAL"
fi

DATABASE_URL_VAL="$(get_env_val DATABASE_URL)"
if is_placeholder "$DATABASE_URL_VAL"; then
  set_env_key "DATABASE_URL" "postgresql+psycopg2://$POSTGRES_USER_VAL:$POSTGRES_PASS_VAL@postgres:5432/$POSTGRES_DB_VAL"
fi

NEO_USER_VAL="$(get_env_val NEO4J_USER)"
NEO_PASS_VAL="$(get_env_val NEO4J_PASSWORD)"
if [[ -z "$NEO_USER_VAL" ]]; then
  NEO_USER_VAL="neo4j"
fi
if is_placeholder "$NEO_PASS_VAL"; then
  NEO_PASS_VAL="$NEO_PASS"
  set_env_key "NEO4J_PASSWORD" "$NEO_PASS_VAL"
fi

NEO_AUTH_VAL="$(get_env_val NEO4J_AUTH)"
if is_placeholder "$NEO_AUTH_VAL"; then
  set_env_key "NEO4J_AUTH" "$NEO_USER_VAL/$NEO_PASS_VAL"
fi

set_default_env_key "DSA_BOOTSTRAP_IMPORT_IF_EMPTY" "true"
set_default_env_key "DSA_BOOTSTRAP_XLSX_PATH" "/app/bootstrap-data/EPP.xlsx"
set_default_env_key "DSA_BOOTSTRAP_ALLOW_MISSING_XLSX" "true"
set_default_env_key "DSA_BOOTSTRAP_FAIL_ON_IMPORT_ERRORS" "true"
set_default_env_key "DSA_BOOTSTRAP_STATE_FILE" "/var/lib/dsa/bootstrap/state.json"
set_default_env_key "BOOTSTRAP_DATA_HOST_DIR" "../.bootstrap-data"

if [[ -n "$PUBLIC_HOST" ]]; then
  HOST_PORT="${PORT_MAPPING%%:*}"
  set_env_key "DJANGO_ALLOWED_HOSTS" "$PUBLIC_HOST,localhost,127.0.0.1"
  set_env_key "DJANGO_CSRF_TRUSTED_ORIGINS" "http://$PUBLIC_HOST:$HOST_PORT,http://localhost"
fi

python3 - "$COMPOSE_FILE" "$PORT_MAPPING" <<'PY'
import re
import sys
from pathlib import Path

compose_file = Path(sys.argv[1])
port_mapping = sys.argv[2]
text = compose_file.read_text()

text = re.sub(r'"[0-9]+:80"', f'"{port_mapping}"', text, count=1)

start = text.find("\n  nginx:\n")
if start != -1:
    next_service = re.search(r"\n  [a-zA-Z0-9_-]+:\n", text[start + 1 :])
    end = (start + 1 + next_service.start()) if next_service else len(text)
    block = text[start:end]

    if "cap_add:" not in block:
        block = block.replace(
            "    cap_drop:\n      - ALL\n",
            "    cap_drop:\n      - ALL\n    cap_add:\n      - NET_BIND_SERVICE\n",
        )

    if "cap_add:" in block:
        required = ["NET_BIND_SERVICE", "CHOWN", "SETGID", "SETUID"]
        if "cap_add:\n" in block:
            head, tail = block.split("cap_add:\n", 1)
            cap_lines = []
            rest = []
            in_caps = True
            for line in tail.splitlines(keepends=True):
                if in_caps and line.startswith("      - "):
                    cap_lines.append(line.strip().replace("- ", ""))
                else:
                    in_caps = False
                    rest.append(line)
            merged = cap_lines[:]
            for item in required:
                if item not in merged:
                    merged.append(item)
            cap_section = "".join(f"      - {item}\n" for item in merged)
            block = f"{head}cap_add:\n{cap_section}{''.join(rest)}"

    text = text[:start] + block + text[end:]

compose_file.write_text(text)
PY

cd "$APP_DIR"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

if [[ "$RUN_SMOKE" == "1" ]]; then
  host_port="${PORT_MAPPING%%:*}"
  smoke_url="${SMOKE_BASE_URL:-http://127.0.0.1:$host_port}"
  ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" PUBLIC_BASE_URL="$smoke_url" scripts/smoke-prod.sh
fi

echo "Deploy finished."
