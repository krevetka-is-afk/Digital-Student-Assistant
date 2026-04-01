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
    db_path="$(mktemp "$tmp_dir/release-gate.XXXXXX.sqlite3")"
    cleanup_db=1
fi

export PYTHONPATH="$repo_root/src/web:$repo_root"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$repo_root/.tmp/uv-cache}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.dev}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$db_path}"
export TEST_DB_URL="${TEST_DB_URL:-$DATABASE_URL}"

if [[ "$cleanup_db" -eq 1 ]]; then
    trap 'rm -f "$db_path"' EXIT
fi

if [[ ! -x "$repo_root/.venv/bin/python" || ! -x "$repo_root/.venv/bin/pytest" ]]; then
    echo "Expected synced workspace environment at .venv. Run: uv sync --all-packages --group dev" >&2
    exit 1
fi

"$repo_root/.venv/bin/python" "$repo_root/src/web/manage.py" migrate --noinput

"$repo_root/.venv/bin/pytest" -q
