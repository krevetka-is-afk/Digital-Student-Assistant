# Digital-Student-Assistant

Цифровой Ассистент Студента - это платформа подбора и сопровождения студенческих проектов. Текущий runtime состоит из Django + DRF backend с role-based личными кабинетами (`student`, `customer`, `cpprp`), отдельного ML-сервиса для поиска/рекомендаций и graph сервиса, который строит связи между студентами, научными руководителями, тегами и заявками из outbox-событий. Этот backend выступает как эволюционный дубликат существующего контура.

![CI](https://github.com/krevetka-is-afk/Digital-Student-Assistant/actions/workflows/ci.yml/badge.svg) [![Deploy Production](https://github.com/krevetka-is-afk/Digital-Student-Assistant/actions/workflows/deploy-prod.yml/badge.svg)](https://github.com/krevetka-is-afk/Digital-Student-Assistant/actions/workflows/deploy-prod.yml)

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
uv sync --all-packages --group dev
export PYTHONPATH=.
```

## Canonical test entrypoint

```bash
uv sync --all-packages --group dev
./scripts/run-release-gate.sh
```

Этот сценарий использует единое workspace-окружение для `web`, `ml`, `graph`, затем `run-release-gate.sh` применяет Django migrations для локальной SQLite-базы и запускает общий `pytest` release gate из корня репозитория.

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
uv run python manage.py import_epp_xlsx --path /absolute/path/to/EPP.xlsx --settings=config.settings.dev
uv run python manage.py runserver --settings=config.settings.dev
```

После запуска:

- Home: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/health/`
- API root: `http://127.0.0.1:8000/api/v1/`
- Account API: `http://127.0.0.1:8000/api/v1/account/me/`
- Recs search: `http://127.0.0.1:8000/api/v1/recs/search/?q=graph`
- ML readiness: `http://127.0.0.1:8001/ready`
- Graph state: `http://127.0.0.1:8002/state`

## Текущий product focus

- Канонический release surface фиксируется в `docs/architecture/contracts/api_contract.json` и проверяется против generated OpenAPI.
- Канонический event surface фиксируется в `docs/architecture/contracts/event_contract.json` и проверяется против фактических `emit_event(...)` вызовов в `src/web/apps/*`.
- Канонический runtime backend сейчас строится вокруг Django API, role-based `account` кабинетов и recommendation flow через `recs` + outbox для downstream `ml`/`graph`.
- `EPP` хранится в `projects` как родительская сущность.
- `Project` представляет vacancy/topic строку из файла и остается основным объектом модерации и заявок.
- `account` предоставляет отдельные role-based кабинеты, но не заменяет существующие `/api/v1/projects/` и `/api/v1/applications/`.
- `SSR` и вузовский `SSO` не реализуются в этой итерации.

## Import

Канонический runtime-контракт для импорта - `POST /api/v1/imports/epp/` с XLSX-файлом. CLI-команда тоже поддерживается, но требует явного доступного пути.

```bash
cd src/web
uv run python manage.py import_epp_xlsx --path /absolute/path/to/EPP.xlsx --settings=config.settings.dev
```

Текущий header contract и нормализация полей зафиксированы в `src/web/apps/projects/importers.py`, а `ImportRun.stats` является каноническим описанием результата импорта.

## Release Contracts

Canonical release contracts live in `docs/architecture/contracts/api_contract.json` and `docs/architecture/contracts/event_contract.json`.
They are validated against generated OpenAPI and current outbox event emitters in `tests/contract/`.

Current release surface includes:

- `projects`, `applications` and their action endpoints for submit/moderate/review flows
- `account/me`, `account/student/overview`, `account/customer/*`, `account/cpprp/*` for role-based personal cabinets
- `users/me` and `users/me/favorites*` for profile and student bookmarks
- `recs/search`, `recs/recommendations`, `recs/reindex` for recommendation/search integration
- `imports/epp` and outbox delivery endpoints (`outbox/events`, `outbox/events/ack`, `outbox/consumers/<consumer>/checkpoint`) for safe downstream graph/ML synchronization

Portable deployment assets live in `infra/docker-compose.prod.yml`, `infra/nginx/default.conf`, `scripts/backup-postgres.sh`, `scripts/restore-postgres.sh`, `docs/deployment_runbook.md`.
Admin login and CSRF topology runbook: `docs/ops/admin-login-http-https.md`.
VM sizing load-test
Executable `k6` scenarios for that runbook live in `perf/k6/`.

## Django settings profiles

```bash
cd src/web
DJANGO_SECRET_KEY=change-me \
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
python manage.py check --deploy --settings=config.settings.prod
```

## Структура проекта

- `src/web/` - Django + DRF сервис
- `src/web/apps/*/tests/{api,unit}/` - локальные тесты web-доменов
- `src/ml/` - FastAPI ML сервис
- `src/graph/` – Neo4J
- `tests/` - межсервисные contract/integration/e2e сценарии
- `infra/` - docker compose и инфраструктурные файлы
- `infra/compose/test/docker-compose.yml` - тестовое окружение для integration flow
- `docs/architecture/` - ADR, contracts и архитектурные документы
- `security/` - security-проверки и конфигурации

## Contribute

```bash
uv run pre-commit install
```

before PR

```bash
./scripts/uv-linters.sh
```

Type checking via `ty` is available as a separate script:

```bash
./scripts/uv-typecheck.sh
```

You can also include it in the lint script explicitly:

```bash
CHECK_TYPES=1 ./scripts/uv-linters.sh
```

## Issues

Now we have two options for issues:

1. [Bug report](.github/ISSUE_TEMPLATE/bug_report.yml)
2. [Feature request](.github/ISSUE_TEMPLATE/feature.yml)
