# API Permission Matrix

This document defines the MVP product-role authorization matrix for the API-first iteration.

## Source of truth

- Product role is stored in `apps.users.models.UserProfile.role`.
- Supported product roles: `student`, `customer`, `cpprp`.
- `Django staff` keeps an administrative override for the endpoints listed below.

## Role matrix

| API surface | Student | Customer | CPPRP | Staff |
| --- | --- | --- | --- | --- |
| `GET /api/v1/projects/`, `GET /api/v1/projects/{id}/` | Catalog only; own private drafts also visible when authenticated | Catalog + own private drafts | Catalog + own private drafts if any | Full visibility through existing staff behavior |
| `POST /api/v1/projects/` | Denied | Allowed | Denied | Allowed |
| `PATCH/PUT/DELETE /api/v1/projects/{id}/` | Denied | Allowed for owned projects only | Denied | Allowed |
| `POST /api/v1/projects/{id}/actions/submit/` | Denied | Allowed for owned projects only | Denied | Allowed |
| `POST /api/v1/projects/{id}/actions/moderate/` | Denied | Denied | Allowed | Allowed |
| `GET/POST /api/v1/applications/` | Allowed for own applications only | Denied | Denied | Allowed |
| `GET/PATCH/DELETE /api/v1/applications/{id}/` | Allowed for own applications only | Denied | Denied | Allowed |
| `POST /api/v1/applications/{id}/actions/review/` | Denied | Allowed for applications of owned projects only | Denied | Allowed |
| `GET /api/v1/account/student/overview/` | Allowed | Denied | Denied | Allowed |
| `GET /api/v1/account/customer/projects/`, `GET /api/v1/account/customer/applications/` | Denied | Allowed | Denied | Allowed |
| `GET /api/v1/account/cpprp/*` moderation/export/configuration endpoints | Denied | Denied | Allowed | Allowed |
| `GET/POST /api/v1/imports/epp/` | Denied | Denied | Allowed | Allowed |
| `POST /api/v1/recs/reindex/` | Denied | Denied | Allowed | Allowed |

## Implementation notes

- Endpoint-level enforcement lives in `apps.account.permissions` through reusable DRF permission classes:
  - `IsStudentOrStaff`
  - `IsCustomerOrStaff`
  - `IsCpprpOrStaff`
- Domain-level transition guards keep the same matrix if business logic is called outside the route layer:
  - `apps.projects.transitions.submit_project_for_moderation`
  - `apps.applications.transitions.review_application`
- Critical CPPRP/staff-only permission denials are logged from `apps.account.permissions`.

## Affected endpoints and tests

- Project permissions and transitions:
  - `src/web/apps/projects/views.py`
  - `src/web/apps/projects/transitions.py`
  - `src/web/apps/projects/tests/api/test_projects_api.py`
  - `src/web/apps/projects/tests/api/test_transitions.py`
- Application permissions and transitions:
  - `src/web/apps/applications/views.py`
  - `src/web/apps/applications/transitions.py`
  - `src/web/apps/applications/tests/api/test_transitions.py`
- Account / operations endpoints:
  - `src/web/apps/account/views.py`
  - `src/web/apps/account/tests/api/test_account_api.py`
  - `src/web/apps/imports/views.py`
  - `src/web/apps/imports/tests/api/test_import_api.py`
  - `src/web/apps/recs/views.py`
  - `src/web/apps/recs/tests/api/test_recs_api.py`
