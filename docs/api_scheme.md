# API Scheme (Canonical v1)

Updated: 2026-03-29

## API Entry Points

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/` | Stable API index with links to versioned and legacy endpoints |
| GET | `/api/schema/` | OpenAPI schema (machine-readable contract) |
| GET | `/api/docs/` | Swagger UI for API schema |
| GET | `/api/v1/` | Canonical API v1 index |
| GET | `/api/legacy/` | Deprecated legacy API root |
| POST | `/api/add/` | Backward-compatible alias for legacy add endpoint |

## Canonical API v1 (`/api/v1/`)

Use these endpoints for manual testing, frontend integration, and release contract review.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/health/` | no | Service liveness |
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
| GET | `/api/v1/projects/` | optional | List projects (`page`, `page_size`, `status`, `q`, `ordering`) |
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
| GET | `/api/v1/account/customer/projects/` | customer/staff | Customer cabinet project list with submitted applications counters |
| GET | `/api/v1/account/customer/applications/` | customer/staff | Customer cabinet incoming applications |
| GET | `/api/v1/account/cpprp/moderation-queue/` | cpprp/staff | CPPRP moderation queue |
| GET | `/api/v1/account/cpprp/applications/` | cpprp/staff | CPPRP applications overview and recent feed |
| GET | `/api/v1/account/cpprp/deadlines/` | cpprp/staff | List platform deadlines |
| POST | `/api/v1/account/cpprp/deadlines/` | cpprp/staff | Create deadline and emit `deadline.changed` |
| GET | `/api/v1/account/cpprp/templates/` | cpprp/staff | List document templates |
| POST | `/api/v1/account/cpprp/templates/` | cpprp/staff | Create document template |
| GET | `/api/v1/account/cpprp/export/projects/` | cpprp/staff | Export projects as CSV |
| GET | `/api/v1/account/cpprp/export/applications/` | cpprp/staff | Export applications as CSV |
| GET | `/api/v1/users/me/` | yes | Get current user's profile |
| PATCH | `/api/v1/users/me/` | yes | Update current user's profile (`role`, `interests`) |
| PUT | `/api/v1/users/me/` | yes | Full update alias for current user's profile |
| GET | `/api/v1/users/me/favorites/` | yes | List bookmarked projects |
| PUT | `/api/v1/users/me/favorites/` | yes | Replace bookmarked project ids |
| POST | `/api/v1/users/me/favorites/` | yes | Append bookmarked project ids |
| DELETE | `/api/v1/users/me/favorites/<id>/` | yes | Remove bookmarked project |
| GET | `/api/v1/recs/search/?q=<text>` | no | Search proxy for recommendation stack |
| GET | `/api/v1/recs/recommendations/` | yes | Personalized recommendations by interests/profile |
| POST | `/api/v1/recs/reindex/` | cpprp/staff | Emit `recs.reindex_requested` event |
| GET | `/api/v1/imports/epp/` | cpprp/staff | List import runs |
| POST | `/api/v1/imports/epp/` | cpprp/staff | Run XLSX import and emit `import.completed` on success |
| GET | `/api/v1/outbox/events/` | cpprp/staff | Read outbox feed with `consumer` checkpoint semantics (`mode=poll|replay`, `since_id`, `replay_from_id`) |
| POST | `/api/v1/outbox/events/ack/` | cpprp/staff | Monotonic ack for consumer checkpoint (`consumer`, `event_id`) |
| GET | `/api/v1/outbox/consumers/<consumer>/checkpoint/` | cpprp/staff | Get consumer resume state (`last_acked_event_id`, `last_seen_event_id`, `status`) |

## Legacy API (compatibility)

These routes remain available, but should be treated as deprecated for new testing.

- `/api/legacy/` and `/api/legacy/add/` (legacy `Item` endpoints)
- `/api/add/` (compatibility alias to legacy add endpoint)
- `/base/` (legacy base/auth/health helper endpoints)
- `/base/projects/` (legacy project endpoints)
- `/base/search` (legacy search endpoint)
- `/base/v2/projects/` (legacy viewset router)

## Lifecycle statuses (I2)

- Project: `draft -> on_moderation -> published/rejected -> staffed` (+ `archived`)
- Initiative proposal: `draft -> on_moderation -> revision_requested -> on_moderation -> published`
- Application: `submitted -> accepted/rejected`
- Direct status transitions via generic `PATCH` are blocked; use action endpoints.

## Release Contract Source of Truth

- Required canonical paths, operations, and OpenAPI schema components live in `docs/architecture/contracts/api_contract.json`.
- Required domain event types live in `docs/architecture/contracts/event_contract.json`.
- `tests/contract/test_openapi_sync.py` validates these requirements against generated `/api/schema/`.
- `tests/contract/test_event_schemas.py` validates the event contract against current `emit_event(...)` calls in the backend.

## Recommendations Gateway Modes

- `semantic`: backend successfully received ranked items from external ML service.
- `keyword-fallback`: backend used local keyword ranking because ML service is unavailable, timed out, or returned invalid payload.

## Outbox Delivery Semantics

- Canonical offset is outbox event `id`.
- `poll` mode: `GET /api/v1/outbox/events/?consumer=<name>` returns events with `id > last_acked_event_id`.
- `ack`: after successful processing, consumer confirms highest processed offset via `POST /api/v1/outbox/events/ack/`.
- Ack is idempotent: repeating the same `event_id` keeps checkpoint unchanged (`ack_status=already_acked`).
- `replay` mode: `GET /api/v1/outbox/events/?consumer=<name>&mode=replay&replay_from_id=<id>` re-reads history from the requested offset and marks each event as `acked|pending` relative to current checkpoint.
- Resume after restart: consumer reads `GET /api/v1/outbox/consumers/<consumer>/checkpoint/` and continues polling from the stored checkpoint.

## Quick browser test flow

1. Open `/api/` and verify links to `/api/v1/`.
2. Open `/api/v1/health/` and check `{"status":"ok"}`.
3. Call `POST /api/v1/auth/token/` in DRF browsable API form.
4. Use token in header: `Authorization: Token <your_token>`.
5. Open `/api/v1/projects/`, `/api/v1/applications/`, `/api/v1/users/me/`.
