# ML service

FastAPI recommendation service with two operating modes:

- request-payload fallback (`/search`, `/recommendations` rank the projects passed in the request);
- outbox-backed local index (`/sync`, `/replay`, optional background poller) that consumes the web outbox as consumer `ml`.

## Environment

- `OUTBOX_BASE_URL` — web base URL for `/api/v1/outbox/...`
- `OUTBOX_CONSUMER` — consumer name, default `ml`
- `OUTBOX_AUTH_HEADER` — auth header for outbox calls when poller is enabled
- `OUTBOX_BATCH_SIZE` — sync batch size
- `OUTBOX_POLL_INTERVAL_SEC` — background poll interval
- `ML_ENABLE_BACKGROUND_POLLER` — enable periodic outbox polling
- `ML_INDEX_STATE_PATH` — JSON file used to persist the local recommendation index/checkpoint mirror
