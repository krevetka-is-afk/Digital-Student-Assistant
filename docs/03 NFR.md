# 3. Нефункциональные требования

Актуализировано: 2026-04-28.

## Нагрузка

Ориентир для приемочных расчетов: осенний пик выбора проектов, примерно 1700 студентов и около 1600 проектных строк/тем. Основные нагруженные сценарии:

- просмотр каталога и карточек проектов;
- поиск и рекомендации;
- подача заявок;
- модерация и review заявок;
- импорт EPP XLSX;
- outbox consumption со стороны ML/graph/faculty consumers.

## Производительность

Целевые ориентиры для production-like проверки:

- `GET /projects/`: p95 < 1s, p99 < 2s;
- `GET /api/v1/projects/`: p95 < 500ms;
- `GET /api/v1/recs/search/`: p95 < 800ms;
- write paths: p95 < 1.5s;
- 5xx < 1%;
- без OOM/restarts и без повторяющихся `502/504` от Nginx.

## Надежность

- PostgreSQL является production-target хранилищем operational data.
- Изменения доменных сущностей проходят через транзакции Django/DRF.
- Outbox delivery использует at-least-once семантику, монотонный ack и checkpoint per consumer.
- Повторная обработка downstream events должна быть идемпотентной.
- Neo4j Community не покрывается автоматическим online backup как production-critical источник правды; source of truth остается `web`/PostgreSQL.

## Безопасность

- Ролевая модель: `student`, `customer`, `cpprp`, `staff`.
- Django admin доступен только staff/superuser.
- Auth текущей итерации: локальный login/register с email verification; token endpoint не должен выдавать токен до подтверждения email.
- Сервисные consumers используют bearer machine tokens для outbox API.
- Production-конфигурация должна хранить секреты вне кода и проходить `manage.py check --deploy`.

## Наблюдаемость

- Health/readiness endpoints: `/health/`, `/ready/`, `/api/v1/health/`, `/api/v1/ready/`.
- Metrics endpoints доступны для web, ML и graph сервисов.
- Observability stack: Prometheus/Grafana без Loki/Tempo/OpenTelemetry в первой итерации.

## Verification

Канонические команды:

```bash
uv sync --all-packages --group dev
./scripts/run-release-gate.sh
./scripts/uv-linters.sh
./scripts/uv-typecheck.sh
```
