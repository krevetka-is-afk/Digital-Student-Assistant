# 4. Технические ограничения и инфраструктура

Актуализировано: 2026-04-28.

## Runtime constraints

- Основной backend/frontend runtime: Django + DRF + Django templates в `src/web`.
- ML и graph реализованы отдельными FastAPI reference services.
- Production-target БД: PostgreSQL.
- Локальные тесты и release gate могут использовать SQLite, кроме graph projection сценариев.
- Graph projection использует Neo4j.
- Контейнеризация: Docker Compose; основные compose-файлы лежат в `infra/`.

## Integration constraints

- `web` является source of truth; downstream-сервисы не должны читать внутреннюю БД напрямую.
- Синхронизация ML/graph/faculty consumers идет через outbox API, snapshot, ack/checkpoint/replay.
- External ML считается usable только при валидном `mode=semantic`; иначе используется keyword fallback.

## Auth constraints

- Основной текущий режим: локальная аутентификация с email verification.
- Service-to-service доступ к outbox endpoints выполняется через bearer machine tokens.

## Deployment constraints

- Production/staging topology задается compose-файлами и deployment scripts в инфраструктурном контуре.
- Автоматический backup покрывает PostgreSQL.
