# ML integration handover

Updated: 2026-04-19

## 1. Bootstrap / snapshot contract

External ML should first call `GET /api/v1/outbox/snapshot/` with a machine bearer token.

Response includes:

- `watermark`: highest visible outbox id at snapshot time;
- `projects`: published/staffed catalog projects;
- `applications`: current applications;
- `user_profiles`: current user profiles.

Recommended cutover:

1. fetch snapshot;
2. build local ML index from snapshot payload;
3. store `watermark`;
4. start `replay/poll` from that watermark via outbox endpoints.

## 2. Tombstone / delete events

The backend now emits:

- `project.deleted`
- `application.deleted`

Consumers must treat them as tombstones and remove corresponding entities from local indices/read models.

## 3. Event payload examples

Canonical examples live in `docs/architecture/contracts/event_contract.json` under `payload_examples`.

## 4. External ML team checklist

- implement `POST /search` and `POST /recommendations` using the thin-gateway request shape;
- authenticate to outbox using configured machine token;
- support bootstrap snapshot ingestion;
- support `poll`, `replay`, `checkpoint`, `ack`;
- process delete tombstones idempotently;
- keep local index independent from `web` database internals;
- return `mode=semantic` only when semantic ranking is actually usable.

## 5. Health / readiness policy

`web` considers ML usable only when ML returns:

- HTTP 2xx;
- valid JSON body;
- `mode=semantic`;
- valid `items` array with `project_id`, `score`, `reason`.

Otherwise `web` falls back to local keyword ranking for that request.
