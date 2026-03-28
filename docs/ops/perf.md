# Query Hygiene Runbook

## Scope

This note covers the current critical API collection paths:

- `GET /api/v1/projects/`
- `GET /api/v1/account/customer/projects/`
- `GET /api/v1/account/customer/applications/`
- `GET /api/v1/account/cpprp/moderation-queue/`
- `GET /api/v1/account/cpprp/applications/`

## Rules

- Keep list endpoints paginated. Do not return large unbounded collections from account or catalog APIs.
- Keep filtering and ordering in the ORM/database layer whenever the filter affects list membership or pagination.
- Use `select_related(...)` for single-value relations used by serializers on hot paths.
- Use `annotate(...)` for counters needed in list serializers instead of per-row `.count()` calls.
- Prefer database-backed `order_by(...)` over Python `sorted(...)`.
- Add regression tests for query budgets on at least two critical collection endpoints before merging performance-sensitive list changes.

## Covered Query-Budget Tests

- `GET /api/v1/projects/`:
  `src/web/apps/projects/tests.py::test_projects_list_is_query_efficient`
- `GET /api/v1/projects/` with DB-backed filtering/order path:
  `src/web/apps/projects/tests.py::test_projects_list_keeps_filters_and_ordering_database_backed`
- `GET /api/v1/account/customer/applications/`:
  `src/web/apps/account/tests.py::test_account_customer_applications_is_query_efficient`
- `GET /api/v1/account/cpprp/applications/`:
  `src/web/apps/account/tests.py::test_account_cpprp_applications_recent_is_paginated_and_query_efficient`

## Current Tradeoffs

- `tech_tag` filtering on `/api/v1/projects/` stays database-backed by matching against the JSON payload text. This keeps pagination and ordering in SQL without introducing a normalized tag table in the current release candidate.
- Computed response fields such as `staffing_state`, `application_window_state`, and `is_favorite` are still assembled in application code for serialization, but list membership and ordering must not depend on Python-side post-processing.
- If tag filtering becomes a higher-scale bottleneck later, move tags into a normalized relation or add a database-specific index strategy instead of reintroducing Python-side filtering.

## Development Slow SQL Visibility

- Development settings emit slow SQL through the `django.db.backends` logger.
- Default threshold: `150ms`
- Account collection endpoints now use page envelopes, and the CPPRP applications overview exposes a nested paginated collection at `recent.results`.
- Override with:

```bash
export DJANGO_SLOW_QUERY_MS=75
```

- Slow queries are logged in the form:

```text
slow-sql duration=0.187s sql=SELECT ... params=(...)
```

## Index Notes

- `projects(status, updated_at)` supports moderation/catalog ordering by recency.
- `projects(owner, updated_at)` supports owner-scoped account lists ordered by recency.
- `projects(application_opened_at)` and `projects(application_deadline)` support database-backed `application_state` filtering.
- Existing application indexes remain the primary support for application timelines ordered by `created_at`.
