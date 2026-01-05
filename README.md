# Digital-Student-Assistant

Цифровой Ассистент Студента - это рекомендательная система студенческих проектов на основе интересов студентов. Большую популярность получили рекомендательные системы на основе больших языковых моделей (LLM). В этом проекте предполагается использование как локальной большой языковой модели (Qwen-14b), так и облачной YandexGPT-5.

![CI](https://github.com/krevetka-is-afk/Digital-Student-Assistant/actions/workflows/ci.yml/badge.svg)

## Быстрый старт

```bash
git submodule update --init --recursive  # или клонируйте с флагом --recurse-submodules
# python3 -m venv .venv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade uv
uv sync --group dev
export PYTHONPATH=.
```

```bash
uvicorn app.main:app --reload
```

## Docker

```bash
docker compose --profile dev up --build
```

## Contribute

```bash
pre-commit install
```

before PR

```bash
ruff check --fix .
black .
isort .
pytest -q
pre-commit run --all-files
```
