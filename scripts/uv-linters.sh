#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export PYTHONPATH="$repo_root"

# Root env is used only for shared linters/checkers.
uv sync --group dev --frozen
(
    cd src/web
    uv sync
)
(
    cd src/ml
    uv sync
)

uv run --group dev ruff check --fix .
uv run --group dev black .
uv run --group dev isort .
(
    cd src/web
    uv run python manage.py migrate --noinput
    uv run --with pytest pytest -q
)
(
    cd src/ml
    uv run --with pytest pytest -q tests
)

if [[ "${CHECK_BUILD:-0}" == "1" ]]; then
    (
        cd src/web
        uv run --with build python -m build
    )
    (
        cd src/ml
        uv run --with build python -m build
    )
fi

uv run --group dev pre-commit run --all-files
