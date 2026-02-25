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
uv venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
uv sync --group dev
export PYTHONPATH=.
```

```bash
uvicorn services.ml.app.main:app --reload
```

## Docker

```bash
docker compose -f infra/docker-compose.yaml --profile dev up --build
```

## Django settings profiles

```bash
cd services/web
python manage.py check --settings=web.settings.dev
python manage.py runserver --settings=web.settings.dev
```

```bash
cd services/web
DJANGO_SECRET_KEY=change-me \
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
python manage.py check --deploy --settings=web.settings.prod
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

```bash
uv run ruff check --fix .
uv run black .
uv run isort .
uv run pytest -q
uv run pre-commit run --all-files
```

## Issues
Now we have two options for issues:
1. [Bug report](.github/ISSUE_TEMPLATE/bug_report.yml)
2. [Feature request](.github/ISSUE_TEMPLATE/feature.yml)
