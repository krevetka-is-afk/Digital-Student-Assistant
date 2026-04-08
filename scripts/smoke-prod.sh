#!/usr/bin/env bash
set -euo pipefail

compose_file="${COMPOSE_FILE:-infra/docker-compose.prod.yml}"
env_file="${ENV_FILE:-infra/.env.prod}"
public_base="${PUBLIC_BASE_URL:-http://127.0.0.1}"
compose_cmd=(docker compose -f "$compose_file" --env-file "$env_file")
retry_count="${SMOKE_RETRY_COUNT:-20}"
retry_delay_sec="${SMOKE_RETRY_DELAY_SEC:-3}"

retry() {
  local n=1
  while true; do
    if "$@"; then
      return 0
    fi
    if (( n >= retry_count )); then
      return 1
    fi
    n=$((n + 1))
    sleep "$retry_delay_sec"
  done
}

check_public() {
  local url="$1"
  local expected="$2"
  local body
  body="$(curl -fsSL "$url")"
  if [[ "$body" != *"$expected"* ]]; then
    echo "[FAIL] $url does not contain expected token: $expected" >&2
    echo "Response: $body" >&2
    exit 1
  fi
  echo "[OK] $url"
}

check_internal_from_web() {
  local url="$1"
  local expected="$2"
  "${compose_cmd[@]}" exec -T web python -c "import sys,urllib.request as u; d=u.urlopen('$url', timeout=5).read().decode(); print(d); sys.exit(0 if '$expected' in d else 1)" >/dev/null
  echo "[OK] internal $url"
}

if [[ ! -f "$env_file" ]]; then
  echo "Missing env file: $env_file" >&2
  exit 1
fi

echo "Running production smoke suite against $compose_file (env: $env_file)"

if ! "${compose_cmd[@]}" ps >/dev/null; then
  echo "[FAIL] docker compose project is not reachable for $compose_file" >&2
  exit 1
fi

retry check_public "$public_base/api/v1/health/" '"status":"ok"' || {
  echo "[FAIL] health endpoint did not stabilize in time" >&2
  exit 1
}
retry check_public "$public_base/api/v1/ready/" '"database":"up"' || {
  echo "[FAIL] readiness endpoint did not stabilize in time" >&2
  exit 1
}
retry check_public "$public_base/api/v1/projects/" '"results"' || {
  echo "[FAIL] projects endpoint did not stabilize in time" >&2
  exit 1
}

retry check_internal_from_web "http://ml:8000/ready" '"status":"ok"' || {
  echo "[FAIL] ml readiness did not stabilize in time" >&2
  exit 1
}
retry check_internal_from_web "http://graph:8002/ready" '"status":"ok"' || {
  echo "[FAIL] graph readiness did not stabilize in time" >&2
  exit 1
}

echo "Smoke suite passed."
