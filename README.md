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

## Docker

```bash
docker compose -f infra/docker-compose.yml --profile dev up --build
```

## Web (Django) локальный запуск

```bash
cd src/web/
cp .env.example .env
uv sync --group dev
uv run python manage.py migrate
uv run python manage.py import_epp_xlsx --settings=config.settings.dev
uv run python manage.py runserver --settings=config.settings.dev
```

После запуска:

- Home: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/health/`
- API root: `http://127.0.0.1:8000/api/v1/`
- Account API: `http://127.0.0.1:8000/api/v1/account/me/`

## Текущий product focus

- Каноническая схема данных берется из `docs/data_source/EPP.xlsx`.
- `EPP` хранится в `projects` как родительская сущность.
- `Project` представляет vacancy/topic строку из файла и остается основным объектом модерации и заявок.
- `account` предоставляет role-based API, но не заменяет существующие `/api/v1/projects/` и `/api/v1/applications/`.
- `SSR` и вузовский `SSO` не реализуются в этой итерации.

## Import

По умолчанию импорт читает файл `docs/data_source/EPP.xlsx`.

```bash
cd src/web
uv run python manage.py import_epp_xlsx --settings=config.settings.dev
```

Подробности mapping и нормализации статусов описаны в `docs/epp-account-workflow.md`.

## Django settings profiles

```bash
cd src/web
DJANGO_SECRET_KEY=change-me \
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
python manage.py check --deploy --settings=config.settings.prod
```

## Структура проекта

- `src/web/` - Django + DRF сервис
- `src/ml/` - FastAPI ML сервис
- `src/graph/` – Neo4J
- `infra/` - docker compose и инфраструктурные файлы
- `docs/` - архитектура, спецификации и заметки
- `security/` - security-проверки и конфигурации

## Contribute

```bash
uv run pre-commit install
```

before PR

```bash
./scripts/uv-linters.sh
```

## Issues

Now we have two options for issues:

1. [Bug report](.github/ISSUE_TEMPLATE/bug_report.yml)
2. [Feature request](.github/ISSUE_TEMPLATE/feature.yml)
