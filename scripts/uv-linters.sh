#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export PYTHONPATH="$repo_root"

# Ensure the workspace tooling environment matches pyproject.toml / uv.lock.
# `--all-packages` installs dependencies for workspace members (services/*),
# which are required when root pytest collects tests across the repository.
uv sync --all-packages --group dev --frozen

uv run --group dev ruff check --fix .
uv run --group dev black .
uv run --group dev isort .
uv run --group dev pytest -q
uv run --group dev pre-commit run --all-files
