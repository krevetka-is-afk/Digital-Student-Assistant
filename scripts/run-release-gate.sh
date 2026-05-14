#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

tmp_dir="${RELEASE_GATE_TMP_DIR:-$repo_root/.tmp}"
mkdir -p "$tmp_dir"

cleanup_db=0
if [[ -n "${RELEASE_GATE_DB_PATH:-}" ]]; then
    db_path="$RELEASE_GATE_DB_PATH"
    mkdir -p "$(dirname "$db_path")"
else
    db_path="$(mktemp "$tmp_dir/release-gate-test.XXXXXX.sqlite3")"
    cleanup_db=1
fi

export PYTHONPATH="$repo_root/src/web:$repo_root"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$repo_root/.tmp/uv-cache}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.dev}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$db_path}"
export TEST_DB_URL="${TEST_DB_URL:-$DATABASE_URL}"
export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
export NEO4J_USER="${NEO4J_USER:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-testtest}"
export ALLOW_NEO4J_RESET="${ALLOW_NEO4J_RESET:-1}"

# Skip Neo4j Docker auto-start when graph integration is allowed to be skipped locally.
# Otherwise `docker run` can fail (daemon down / no Docker) and exit the whole script due to set -e
# before pytest runs — even though tests/integration would pytest.skip with ALLOW_LOCAL_GRAPH_SKIP=1.
if [[ "${ALLOW_LOCAL_GRAPH_SKIP:-0}" == "1" ]]; then
    export ALLOW_AUTO_START_NEO4J=0
fi

neo4j_container=""

is_neo4j_reachable() {
    "$repo_root/.venv/bin/python" - <<'PY'
import os
import socket
from urllib.parse import urlparse

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
parsed = urlparse(uri)
host = parsed.hostname or "localhost"
port = parsed.port or 7687
sock = socket.socket()
sock.settimeout(0.6)
try:
    sock.connect((host, port))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
raise SystemExit(0)
PY
}

start_temp_neo4j_if_needed() {
    if is_neo4j_reachable; then
        return 0
    fi
    if [[ "${ALLOW_AUTO_START_NEO4J:-1}" != "1" ]]; then
        return 0
    fi
    if ! command -v docker >/dev/null 2>&1; then
        return 0
    fi
    neo4j_container="dsa-release-gate-neo4j"
    docker rm -f "$neo4j_container" >/dev/null 2>&1 || true
    docker run -d \
        --name "$neo4j_container" \
        -p 7687:7687 \
        -e "NEO4J_AUTH=${NEO4J_USER}/${NEO4J_PASSWORD}" \
        neo4j:5-community >/dev/null
    for _ in $(seq 1 45); do
        if is_neo4j_reachable; then
            return 0
        fi
        sleep 1
    done
    echo "Neo4j was auto-started but is still unreachable at ${NEO4J_URI}." >&2
    return 1
}

cleanup() {
    if [[ "$cleanup_db" -eq 1 ]]; then
        rm -f "$db_path"
    fi
    if [[ -n "$neo4j_container" ]]; then
        docker rm -f "$neo4j_container" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

if [[ ! -x "$repo_root/.venv/bin/python" || ! -x "$repo_root/.venv/bin/pytest" ]]; then
    echo "Expected synced workspace environment at .venv. Run: uv sync --all-packages --group dev" >&2
    exit 1
fi

start_temp_neo4j_if_needed

"$repo_root/.venv/bin/python" "$repo_root/src/web/manage.py" migrate --noinput

"$repo_root/.venv/bin/pytest" -q
