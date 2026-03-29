# Project Structure (Actual State)

Updated: 2026-03-29

```txt
Digital-Student-Assistant/
├─ README.md
├─ LICENSE
├─ EVIDENCE/
├─ .github/
│  ├─ workflows/
│  │  └─ ci.yml
│  └─ ISSUE_TEMPLATE/
├─ docs/
│  ├─ architecture/
│  │  ├─ adr/
│  │  ├─ contracts/
│  │  └─ permissions.md
│  ├─ issues/
│  ├─ ops/
│  ├─ technical-specification/
│  │  └─ technical-specification-3/
│  ├─ 01 General objectives and context of the project.md
│  ├─ 02 Functional requirements.md
│  ├─ 03 NFR.md
│  ├─ 04 Limits.md
│  ├─ 05 Support, development, operation.md
│  ├─ 10 architectural decision.md
│  └─ structure_of_project.md
├─ infra/
│  ├─ compose/
│  │  └─ test/
│  │     └─ docker-compose.yml
│  ├─ docker-compose.yml
│  ├─ docker-compose.dev.yml
│  ├─ docker-compose.prod.yml
│  └─ nginx/
├─ scripts/
│  ├─ backup-postgres.sh
│  ├─ restore-postgres.sh
│  └─ uv-linters.sh
├─ security/
│  ├─ seccomp/
│  └─ semgrep/
├─ src/
│  ├─ web/                         # Django + DRF
│  │  ├─ Dockerfile
│  │  ├─ pyproject.toml
│  │  ├─ uv.lock
│  │  ├─ manage.py
│  │  ├─ config/
│  │  ├─ apps/
│  │  │  ├─ account/
│  │  │  │  └─ tests/
│  │  │  │     └─ api/
│  │  │  ├─ applications/
│  │  │  │  └─ tests/
│  │  │  │     ├─ api/
│  │  │  │     └─ unit/
│  │  │  ├─ base/
│  │  │  │  └─ tests/
│  │  │  │     ├─ api/
│  │  │  │     ├─ integration/
│  │  │  │     └─ unit/
│  │  │  ├─ imports/
│  │  │  │  └─ tests/
│  │  │  │     └─ api/
│  │  │  ├─ outbox/
│  │  │  │  └─ tests/
│  │  │  │     └─ api/
│  │  │  ├─ projects/
│  │  │  │  └─ tests/
│  │  │  │     ├─ api/
│  │  │  │     └─ unit/
│  │  │  ├─ recs/
│  │  │  │  └─ tests/
│  │  │  │     └─ api/
│  │  │  ├─ search/
│  │  │  │  └─ tests/
│  │  │  │     └─ api/
│  │  │  ├─ tags/
│  │  │  │  └─ tests/
│  │  │  │     └─ api/
│  │  │  └─ users/
│  │  │     └─ tests/
│  │  │        ├─ api/
│  │  │        └─ unit/
│  │  ├─ client/
│  │  ├─ templates/
│  │  └─ tests/                    # shared web-level suites
│  │     ├─ api/
│  │     ├─ contract/
│  │     ├─ integration/
│  │     └─ unit/
│  ├─ ml/                          # FastAPI ML service
│  │  ├─ Dockerfile
│  │  ├─ pyproject.toml
│  │  ├─ uv.lock
│  │  ├─ app/
│  │  └─ tests/
│  │     ├─ api/
│  │     ├─ contract/
│  │     ├─ integration/
│  │     └─ unit/
│  └─ graph/                       # graph projector service
│     ├─ Dockerfile
│     ├─ pyproject.toml
│     ├─ app/
│     └─ tests/
│        ├─ integration/
│        └─ unit/
├─ tests/                          # repository-level tests
│  ├─ contract/
│  ├─ e2e/
│  └─ integration/
│     └─ conftest.py
├─ pyproject.toml
└─ uv.lock
```

## Web Domain Apps (`src/web/apps`)

- `base`: authentication, permissions, shared API endpoints, health endpoint.
- `projects`: main project domain (models, serializers, validators, viewsets).
- `applications`: application workflow domain.
- `search`: search endpoints/domain.
- `tags`: tags domain scaffold.
- `imports`: import pipeline and tracked import runs.
- `outbox`: event feed read model.
- `account`: role-scoped account and CPPRP operations endpoints.
- `api`: top-level DRF API wiring.

## Web Test Layout

- `src/web/apps/<app>/tests/api/`: endpoint and permission behavior for one Django app.
- `src/web/apps/<app>/tests/unit/`: model, admin, importer, and other isolated app tests.
- `src/web/tests/`: shared web-level suites that span several Django apps.
- `tests/`: repository-level contract, integration, and e2e suites across services.

## Notes

- `src/graph/` and `src/ml/` keep service-local tests, which is consistent for multi-package services.
- `docs/architecture/contracts/` is the canonical location for API and event contracts.
- `docs/architecture/adr/` keeps architectural decisions next to the rest of the architecture assets.
- `infra/compose/test/docker-compose.yml` holds the integration test environment definition.
