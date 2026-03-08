# API Scheme (MVP)

Updated: 2026-03-08

## API Entry Points

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/` | Stable API index with links to versioned and legacy endpoints |
| GET | `/api/v1/` | Canonical API v1 index |
| GET | `/api/legacy/` | Deprecated legacy API root |
| POST | `/api/add/` | Backward-compatible alias for legacy add endpoint |

## Canonical API v1 (`/api/v1/`)

Use these endpoints for manual testing and frontend integration.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/health/` | no | Service liveness |
| POST | `/api/v1/auth/token/` | no | Obtain DRF token by `username/password` |
| GET | `/api/v1/search/?q=<text>` | optional | Search published projects (plus own projects for logged-in user) |
| GET | `/api/v1/projects/` | optional | List projects |
| POST | `/api/v1/projects/` | yes | Create project (owner = current user) |
| GET | `/api/v1/projects/<id>/` | optional | Get project by id |
| PATCH | `/api/v1/projects/<id>/` | yes | Update project (owner or staff) |
| DELETE | `/api/v1/projects/<id>/` | yes | Delete project (owner or staff) |
| GET | `/api/v1/applications/` | yes | List own applications (staff sees all) |
| POST | `/api/v1/applications/` | yes | Create application (applicant = current user) |
| GET | `/api/v1/applications/<id>/` | yes | Get application by id |
| PATCH | `/api/v1/applications/<id>/` | yes | Update application (owner or staff) |
| DELETE | `/api/v1/applications/<id>/` | yes | Delete application (owner or staff) |
| GET | `/api/v1/users/me/` | yes | Get current user's profile |
| PATCH | `/api/v1/users/me/` | yes | Update current user's profile (`role`, `interests`) |

## Legacy API (compatibility)

These routes remain available, but should be treated as deprecated for new testing.

- `/api/legacy/` and `/api/legacy/add/` (legacy `Item` endpoints)
- `/api/add/` (compatibility alias to legacy add endpoint)
- `/base/` (legacy base/auth/health helper endpoints)
- `/base/projects/` (legacy project endpoints)
- `/base/search` (legacy search endpoint)
- `/base/v2/projects/` (legacy viewset router)

## Quick browser test flow

1. Open `/api/` and verify links to `/api/v1/`.
2. Open `/api/v1/health/` and check `{"status":"ok"}`.
3. Call `POST /api/v1/auth/token/` in DRF browsable API form.
4. Use token in header: `Authorization: Bearer <your_token>`.
5. Open `/api/v1/projects/`, `/api/v1/applications/`, `/api/v1/users/me/`.
