# External connector boundary for ML, Graph and Faculty

Updated: 2026-04-28

## Positioning

For team collaboration, `ml`, `graph` and faculty-related integrations should be treated as **external downstream connectors/consumers**, not as owners of the core domain model.

- `web` is the **source of truth** for users, projects, applications, deadlines, faculty mirror data, project-faculty matches and moderation state.
- `ml`, `graph` and faculty integration jobs are **consumers of web-owned contracts**.
- The local `src/ml` and `src/graph` packages in this repository should be presented as **reference consumer implementations / integration harnesses**, not as mandatory production implementations for every team.

This lets another team build their own ML service while still integrating safely with the platform.

## What `web` offers to connector teams

### 1. Synchronous contract (`web -> ML`)

Thin gateway request/response over REST:

- `POST /search`
- `POST /recommendations`
- `POST /reindex`

The gateway now sends only query intent (`query`, `interests`, `limit`).

### 2. Asynchronous contract (`web -> downstream consumers`)

Outbox delivery API:

- `GET /api/v1/outbox/events/`
- `POST /api/v1/outbox/events/ack/`
- `GET /api/v1/outbox/consumers/<consumer>/checkpoint/`
- `GET /api/v1/outbox/snapshot/`

Semantics are fixed by:

- `docs/architecture/contracts/event_contract.json`
- `docs/architecture/contracts/outbox_delivery_contract.json`
- `docs/api_scheme.md`

### 3. Machine authentication

Downstream consumers authenticate with bearer service tokens configured in:

- `OUTBOX_SERVICE_TOKENS`

Example:

```json
{"ml":"ml-secret-token","graph":"graph-secret-token","faculty":"faculty-secret-token"}
```

## What we expect from ML / Graph / Faculty teams

### ML team

Must support:

- thin-gateway REST contract for ranking/search;
- local indexed/read-model ownership on their side;
- idempotent outbox consumption;
- replay from offset;
- monotonic ack after successful processing.

Should align on:

- ranking response shape (`project_id`, `score`, `reason`, `mode`);
- timeout/error behavior;
- bootstrap/snapshot import process;
- delete/tombstone handling.

### Graph team

Must support:

- idempotent projection from outbox events;
- replay from offset;
- monotonic ack;
- local graph schema evolution independent from `web` internals.

Should align on:

- node/edge ownership assumptions;
- graph refresh/rebuild procedure;
- delete/tombstone semantics.

### Faculty integration

Must support:

- synchronization through `sync_faculty` or an equivalent import job;
- stable `source_key` values for faculty persons;
- idempotent writes for persons, publications, courses and project-faculty matches.

Should align on:

- external faculty API availability and timeout behavior;
- stale-record handling;
- supervisor matching rules and confidence/status semantics.

## Recommended collaboration model

### Contract ownership

- `web` team owns the published API/event schemas.
- connector teams own internal implementation behind those schemas.
- breaking changes require versioning or additive rollout.

### Review artifacts for cross-team agreement

Before connector work starts, align on:

1. OpenAPI / JSON contract files.
2. Example payloads for every required event type.
3. Auth mechanism (service token rotation/ownership).
4. Replay/bootstrap procedure.
5. Error handling and SLA assumptions.

### Change policy

- Prefer additive fields.
- Do not reuse event types with changed meaning.
- When semantics change materially, create a new versioned contract or a new event type.
