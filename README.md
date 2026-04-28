# Digital-Student-Assistant

Digital Student Assistant - платформа для подбора и сопровождения студенческих проектов. Текущий контур системы включает веб-сервис на Django + DRF, интерфейс на Django templates, ролевые кабинеты (`student`, `customer`, `cpprp`), локальную аутентификацию с подтверждением адреса электронной почты, ML-сервис для поиска и рекомендаций и graph-сервис, который строит связи между студентами, научными руководителями, тегами и заявками на основе outbox-событий. Компонент `web` остается источником правды для пользователей, проектов, заявок, сроков, импортов и модерационных статусов.

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

## Основная команда проверки

```bash
uv sync --all-packages --group dev
./scripts/run-release-gate.sh
```

Сценарий использует единое рабочее окружение для `web`, `ml` и `graph`, затем `run-release-gate.sh` применяет миграции Django для локальной SQLite-базы и запускает общий `pytest` из корня репозитория.

## Docker

```bash
docker compose -f infra/docker-compose.yml --profile dev up --build
```

## Локальный запуск веб-сервиса

```bash
cd src/web/
cp .env.example .env
uv sync --group dev
uv run python manage.py migrate
uv run python manage.py import_epp_xlsx --path /absolute/path/to/EPP.xlsx --settings=config.settings.dev
uv run python manage.py runserver --settings=config.settings.dev
```

После запуска:

- главная страница: `http://127.0.0.1:8000/`;
- health-check: `http://127.0.0.1:8000/health/`;
- корень API: `http://127.0.0.1:8000/api/v1/`;
- кабинет пользователя: `http://127.0.0.1:8000/api/v1/account/me/`;
- поиск рекомендаций: `http://127.0.0.1:8000/api/v1/recs/search/?q=graph`;
- готовность ML-сервиса: `http://127.0.0.1:8001/ready`;
- состояние graph-сервиса: `http://127.0.0.1:8002/state`.

## Текущий фокус проекта

- Канонический контракт релиза фиксируется в `docs/architecture/contracts/api_contract.json` и сверяется с автоматически сгенерированной OpenAPI-схемой.
- Канонический контракт событий фиксируется в `docs/architecture/contracts/event_contract.json` и сверяется с фактическими вызовами `emit_event(...)` в `src/web/apps/*`.
- Текущий контур выполнения строится вокруг Django API, интерфейса на Django templates, ролевых кабинетов `account` и сценария рекомендаций через `recs` и outbox для сервисов `ml`, `graph` и `faculty`.
- `EPP` хранится в `projects` как родительская сущность.
- `Project` представляет отдельную тему или вакансию из импортируемого набора и остается основным объектом модерации и заявок.
- `account` предоставляет отдельные ролевые кабинеты, но не заменяет существующие `/api/v1/projects/` и `/api/v1/applications/`.
- Интерфейс реализован на Django templates. Основной режим аутентификации в текущей итерации - локальная регистрация и вход с подтверждением email.

## Импорт данных

Канонический контракт импорта - `POST /api/v1/imports/epp/` с XLSX-файлом. Команда командной строки также поддерживается, но требует явного доступного пути.

```bash
cd src/web
uv run python manage.py import_epp_xlsx --path /absolute/path/to/EPP.xlsx --settings=config.settings.dev
```

Текущий контракт заголовков и нормализация полей зафиксированы в `src/web/apps/projects/importers.py`, а `ImportRun.stats` служит каноническим описанием результата импорта.

## Контракты релиза

Канонические контракты релиза расположены в `docs/architecture/contracts/api_contract.json` и `docs/architecture/contracts/event_contract.json`. Они проверяются по сгенерированной OpenAPI-схеме и по актуальным источникам outbox-событий в `tests/contract/`.

Текущий состав релизного контура включает:

- `projects`, `applications` и их специальные методы для отправки, модерации и рассмотрения заявок;
- `account/me`, `account/student/overview`, `account/customer/*`, `account/cpprp/*` для ролевых личных кабинетов;
- `users/me` и `users/me/favorites*` для профиля и избранных проектов студента;
- `recs/search`, `recs/recommendations`, `recs/reindex` для интеграции поиска и рекомендаций;
- `faculty/persons*` для зеркала данных преподавателей и сопоставления проектов с научными руководителями;
- `imports/epp` и outbox-методы (`outbox/events`, `outbox/events/ack`, `outbox/consumers/<consumer>/checkpoint`, `outbox/snapshot`) для безопасной синхронизации с `graph`, `ml` и `faculty`.

Файлы развертывания расположены в `infra/docker-compose.prod.yml`, `infra/nginx/default.conf`, `scripts/backup-postgres.sh` и `scripts/restore-postgres.sh`. Отдельная инструкция по входу в административную панель и топологии CSRF находится в `docs/issues/admin-login-http-https.md`. Выполнимые сценарии `k6` для оценки размеров VM находятся в `perf/k6/`.

## Django settings profiles

```bash
cd src/web
DJANGO_SECRET_KEY=change-me \
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
python manage.py check --deploy --settings=config.settings.prod
```

## Структура проекта

- `src/web/` - сервис Django + DRF;
- `src/web/apps/frontend/` - интерфейс на Django templates;
- `src/web/apps/*/tests/{api,unit}/` - локальные тесты web-доменов
- `src/ml/` - FastAPI ML-сервис;
- `src/graph/` - сервис проекции графа на Neo4j;
- `tests/` - межсервисные contract/integration/e2e-сценарии;
- `infra/` - Docker Compose и инфраструктурные файлы;
- `infra/compose/test/docker-compose.yml` - тестовое окружение для интеграционного контура;
- `docs/architecture/` - ADR, контракты и архитектурные документы;
- `security/` - проверки безопасности и конфигурация.

## Разработка

```bash
uv run pre-commit install
```

Перед созданием pull request:

```bash
./scripts/uv-linters.sh
```

Проверка типов через `ty` вынесена в отдельный сценарий:

```bash
./scripts/uv-typecheck.sh
```

При необходимости ее можно явно включить в сценарий линтеров:

```bash
CHECK_TYPES=1 ./scripts/uv-linters.sh
```

## Сообщения об ошибках и предложениях

Доступны два шаблона issue:

1. [Bug report](.github/ISSUE_TEMPLATE/bug_report.yml)
2. [Feature request](.github/ISSUE_TEMPLATE/feature.yml)
