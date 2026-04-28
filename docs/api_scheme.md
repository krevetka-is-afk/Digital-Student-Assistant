# Схема API (Canonical v1)

Актуализировано: 2026-04-29

## Точки входа API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/` | Stable API index with links to versioned endpoints |
| GET | `/api/schema/` | OpenAPI schema (machine-readable contract) |
| GET | `/api/docs/` | Swagger UI for API schema |
| GET | `/api/v1/` | Canonical API v1 index |

## Канонический API v1 (`/api/v1/`)

Эти методы используются для ручной проверки, интеграции интерфейса и контроля релизного контракта.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/health/` | no | Service liveness |
| GET | `/api/v1/ready/` | no | Service readiness (DB connectivity) |
| POST | `/api/v1/auth/token/` | no | Obtain DRF token by `username/password` |
| GET | `/api/v1/search/?q=<text>` | optional | Search published projects (plus own projects for logged-in user) |
| GET | `/api/v1/initiative-proposals/` | yes | List initiative proposals (owner sees own, CPPRP/staff sees all) |
| POST | `/api/v1/initiative-proposals/` | student/staff | Create initiative proposal |
| POST | `/api/v1/initiative-proposals/<id>/actions/submit/` | student/staff | Submit initiative proposal to CPPRP |
| POST | `/api/v1/initiative-proposals/<id>/actions/moderate/` | cpprp/staff | Moderate initiative proposal (`decision=approve/reject`) |
| GET | `/api/v1/initiative-proposals/<id>/` | yes | Get initiative proposal by id |
| PUT | `/api/v1/initiative-proposals/<id>/` | student/staff | Full update of initiative proposal in editable states |
| PATCH | `/api/v1/initiative-proposals/<id>/` | student/staff | Update initiative proposal in editable states |
| DELETE | `/api/v1/initiative-proposals/<id>/` | student/staff | Delete initiative proposal in editable states |
| GET | `/api/v1/projects/` | optional | List projects (`page`, `page_size`, `status`, `q`, `ordering`, `staffing_state`, `application_state`, `application_window_state`) |
| POST | `/api/v1/projects/` | yes | Create project (owner = current user) |
| POST | `/api/v1/projects/<id>/actions/submit/` | yes | Submit project for moderation (owner/staff) |
| POST | `/api/v1/projects/<id>/actions/moderate/` | yes | Moderate project (`decision=approve/reject`, CPPRP/staff) |
| GET | `/api/v1/projects/<id>/` | optional | Get project by id |
| PATCH | `/api/v1/projects/<id>/` | yes | Update project (owner or staff) |
| DELETE | `/api/v1/projects/<id>/` | yes | Delete project (owner or staff) |
| GET | `/api/v1/applications/` | yes | List own applications (staff sees all) |
| POST | `/api/v1/applications/` | yes | Create application (applicant = current user) |
| POST | `/api/v1/applications/<id>/actions/review/` | yes | Review application (`decision=accept/reject`, owner/staff) |
| GET | `/api/v1/applications/<id>/` | yes | Get application by id |
| PATCH | `/api/v1/applications/<id>/` | yes | Update application (owner or staff) |
| DELETE | `/api/v1/applications/<id>/` | yes | Delete application (owner or staff) |
| GET | `/api/v1/account/me/` | yes | Role-aware cabinet counters and current profile summary |
| GET | `/api/v1/account/student/overview/` | student/staff | Student cabinet overview with applications, favorites, deadlines, templates |
| GET | `/api/v1/account/customer/projects/` | customer/staff | Customer cabinet project list with `applications_count` and `submitted_applications_count` |
| GET | `/api/v1/account/customer/applications/` | customer/staff | Customer cabinet incoming applications (`status` filter supported) |
| GET | `/api/v1/account/cpprp/moderation-queue/` | cpprp/staff | CPPRP moderation queue |
| GET | `/api/v1/account/cpprp/applications/` | cpprp/staff | CPPRP applications overview and recent feed (`status` filter for recent feed) |
| GET | `/api/v1/account/cpprp/deadlines/` | cpprp/staff | List platform deadlines |
| POST | `/api/v1/account/cpprp/deadlines/` | cpprp/staff | Create deadline and emit `deadline.changed` |
| GET | `/api/v1/account/cpprp/templates/` | cpprp/staff | List document templates |
| POST | `/api/v1/account/cpprp/templates/` | cpprp/staff | Create document template |
| GET | `/api/v1/account/templates/<id>/download/` | yes | Unified template download endpoint (role/audience aware) |
| GET | `/api/v1/account/cpprp/export/projects/` | cpprp/staff | Export projects as CSV |
| GET | `/api/v1/account/cpprp/export/applications/` | cpprp/staff | Export applications as CSV |
| GET | `/api/v1/users/me/` | yes | Get current user's profile |
| PATCH | `/api/v1/users/me/` | yes | Update current user's profile (`role`, `interests`) |
| PUT | `/api/v1/users/me/` | yes | Full update alias for current user's profile |
| GET | `/api/v1/users/me/favorites/` | yes | List bookmarked projects |
| PUT | `/api/v1/users/me/favorites/` | yes | Replace bookmarked project ids |
| POST | `/api/v1/users/me/favorites/` | yes | Append bookmarked project ids |
| DELETE | `/api/v1/users/me/favorites/<id>/` | yes | Remove bookmarked project |
| GET | `/api/v1/faculty/persons/` | optional | List non-stale HSE faculty persons (`q`, `interest`) |
| GET | `/api/v1/faculty/persons/<source_key>/` | optional | Get one faculty person mirror record |
| GET | `/api/v1/faculty/persons/<source_key>/projects/` | optional | List confirmed public project matches for one faculty person |
| GET | `/api/v1/recs/search/?q=<text>` | no | Search proxy for recommendation stack |
| GET | `/api/v1/recs/recommendations/` | yes | Personalized recommendations by interests/profile |
| POST | `/api/v1/recs/reindex/` | cpprp/staff | Emit `recs.reindex_requested` event |
| GET | `/api/v1/imports/epp/` | cpprp/staff | List import runs |
| POST | `/api/v1/imports/epp/` | cpprp/staff | Run XLSX import and emit `import.completed` on success |
| GET | `/api/v1/outbox/events/` | cpprp/staff or machine consumer token | Read outbox feed with `consumer` checkpoint semantics (`mode=poll|replay`,`since_id`,`replay_from_id`) |
| POST | `/api/v1/outbox/events/ack/` | cpprp/staff or machine consumer token | Monotonic ack for consumer checkpoint (`consumer`, `event_id`) |
| GET | `/api/v1/outbox/consumers/<consumer>/checkpoint/` | cpprp/staff or machine consumer token | Get consumer resume state (`last_acked_event_id`, `last_seen_event_id`, `status`) |
| GET | `/api/v1/outbox/snapshot/` | cpprp/staff or machine consumer token | Bootstrap snapshot for downstream consumers (`watermark`, `projects`, `applications`, `user_profiles`, optional faculty resources) |

## Устаревшие веб-методы

Проект по-прежнему содержит устаревшие неканонические маршруты вне `/api/v1/`.
Они не входят в основной контракт API и не должны использоваться в новых интеграциях:

- `/base/` (legacy base/auth/health helper endpoints)
- `/base/projects/` (legacy project endpoints)
- `/base/search` (legacy search endpoint)
- `/base/v2/projects/` (legacy viewset router)

## Статусы жизненного цикла (I2)

- Project: `draft -> on_moderation -> published/rejected -> staffed` (+ `archived`)
- Initiative proposal: `draft -> on_moderation -> revision_requested -> on_moderation -> published`
- Application: `submitted -> accepted/rejected`
- Прямые переходы между статусами через общий `PATCH` запрещены; нужно использовать специальные методы API.

## Источник истины для релизного контракта

- Обязательные маршруты, операции и компоненты OpenAPI-схемы зафиксированы в `docs/architecture/contracts/api_contract.json`.
- Обязательные типы доменных событий зафиксированы в `docs/architecture/contracts/event_contract.json`.
- Семантика доставки outbox-событий и snapshot описана в `docs/architecture/contracts/outbox_delivery_contract.json`.
- `tests/contract/test_openapi_sync.py` проверяет эти требования по сгенерированному `/api/schema/`.
- `tests/contract/test_event_schemas.py` проверяет контракт событий по актуальным вызовам `emit_event(...)` в backend.

## Режимы шлюза рекомендаций

- `semantic`: backend успешно получил ранжированные элементы от внешнего ML-сервиса.
- `keyword-fallback`: backend использовал локальное ранжирование по ключевым словам, потому что ML-сервис недоступен, превысил время ожидания или вернул некорректный ответ.

## Семантика доставки outbox-событий

- Каноническим смещением служит `id` outbox-события.
- Режим `poll`: `GET /api/v1/outbox/events/?consumer=<name>` возвращает события с `id > last_acked_event_id`.
- `ack`: после успешной обработки потребитель подтверждает наибольшее обработанное смещение через `POST /api/v1/outbox/events/ack/`.
- Подтверждение идемпотентно: повторная отправка того же `event_id` не меняет контрольную точку (`ack_status=already_acked`).
- Режим `replay`: `GET /api/v1/outbox/events/?consumer=<name>&mode=replay&replay_from_id=<id>` повторно читает историю с указанного смещения и помечает каждое событие как `acked|pending` относительно текущей контрольной точки.
- После перезапуска потребитель читает `GET /api/v1/outbox/consumers/<consumer>/checkpoint/` и продолжает опрос с сохраненной позиции.

## Быстрая проверка в браузере

1. Open `/api/` and verify links to `/api/v1/`.
2. Open `/api/v1/health/` and check `{"status":"ok"}`.
3. Open `/api/v1/ready/` and check `{"status":"ok"}`.
4. Call `POST /api/v1/auth/token/` in DRF browsable API form.
5. Use token in header: `Authorization: Token <your_token>`.
6. Open `/api/v1/projects/`, `/api/v1/applications/`, `/api/v1/users/me/`.

## Машинная аутентификация потребителей outbox

- Outbox-методы поддерживают bearer machine tokens для сервисов `ml`, `graph` и интеграционных задач, связанных с `faculty`.
- Токены задаются в `OUTBOX_SERVICE_TOKENS` как JSON-объект: `{"ml":"...","graph":"..."}`.
- Пользователи также могут обращаться к outbox-методам через существующие права `cpprp/staff`.

## API зеркала преподавателей

`/api/v1/faculty/*` предоставляет read-only зеркало данных преподавателей НИУ ВШЭ и рассчитанные сопоставления проектов с научными руководителями, которые хранятся в `apps.faculty`.

- `GET /api/v1/faculty/persons/?q=<text>&interest=<text>` lists active faculty records.
- `GET /api/v1/faculty/persons/<source_key>/` returns one faculty record.
- `GET /api/v1/faculty/persons/<source_key>/projects/` returns confirmed project matches whose projects are visible in the catalog.

Данные о преподавателях также могут входить в outbox snapshot через дополнительные ресурсы: `faculty_persons`, `faculty_publications`, `faculty_courses`, `project_faculty_matches`.

## Политика готовности ML-интеграции

`web` считает внешний ML-сервис пригодным для использования только в том случае, если он возвращает успешный JSON-ответ 2xx с `mode=semantic` и корректным массивом `items` (`project_id`, `score`, `reason`). Во всех остальных случаях - при тайм-ауте, ошибке 5xx, некорректном JSON, неверных элементах или другом режиме - `web` переключается на локальный `keyword-fallback` для текущего запроса.
