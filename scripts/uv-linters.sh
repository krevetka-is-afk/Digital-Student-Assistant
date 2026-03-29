#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export PYTHONPATH="$repo_root"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$repo_root/.tmp/uv-cache}"

mkdir -p "$repo_root/.tmp"

# Keep a single workspace environment. Per-package `uv sync` calls mutate the same
# `.venv` and can evict shared dev tools such as ruff/black/isort/pre-commit.
uv sync --all-packages --group dev --frozen

python_bin="$repo_root/.venv/bin/python"
pytest_bin="$repo_root/.venv/bin/pytest"
ruff_bin="$repo_root/.venv/bin/ruff"
black_bin="$repo_root/.venv/bin/black"
isort_bin="$repo_root/.venv/bin/isort"
pre_commit_bin="$repo_root/.venv/bin/pre-commit"

"$ruff_bin" check --fix .
"$black_bin" .
"$isort_bin" .

(
    cd src/web
    "$python_bin" manage.py migrate --noinput
    "$pytest_bin" -q
)
(
    cd src/ml
    "$pytest_bin" -q tests
)

if [[ "${CHECK_BUILD:-0}" == "1" ]]; then
    (
        cd src/web
        "$python_bin" -m build
    )
    (
        cd src/ml
        "$python_bin" -m build
    )
fi

"$pre_commit_bin" run --all-files
