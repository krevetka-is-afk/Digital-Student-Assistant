#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export PYTHONPATH="$repo_root"

# Root env is used only for shared linters/checkers.
uv sync --group dev --frozen
(
    cd services/web
    uv sync
)
(
    cd services/ml
    uv sync
)

uv run --group dev ruff check --fix .
uv run --group dev black .
uv run --group dev isort .
(
    cd services/web
    uv run --with pytest pytest -q apps/base/tests/tests.py
)
(
    cd services/ml
    uv run --with pytest pytest -q tests
)
uv run --group dev pre-commit run --all-files
