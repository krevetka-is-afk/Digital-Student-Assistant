# Project Structure (Actual State)

Updated: 2026-03-07

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
│  ├─ adr/
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
│  ├─ docker-compose.yml
│  ├─ docker-compose.dev.yml
│  └─ .dockerignore
├─ scripts/
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
│  │  │  ├─ settings/
│  │  │  │  ├─ base.py
│  │  │  │  ├─ dev.py
│  │  │  │  └─ prod.py
│  │  │  ├─ urls.py
│  │  │  ├─ routers.py
│  │  │  ├─ asgi.py
│  │  │  └─ wsgi.py
│  │  ├─ apps/
│  │  │  ├─ api/
│  │  │  ├─ applications/
│  │  │  ├─ base/
│  │  │  ├─ imports/
│  │  │  ├─ outbox/
│  │  │  ├─ projects/
│  │  │  ├─ search/
│  │  │  └─ tags/
│  │  ├─ templates/
│  │  │  └─ home.html
│  │  ├─ client/                   # local API client scripts
│  │  └─ tests/                    # scaffolds: unit/api/integration/contract
│  ├─ ml/                          # FastAPI ML service
│  │  ├─ Dockerfile
│  │  ├─ pyproject.toml
│  │  ├─ uv.lock
│  │  ├─ app/
│  │  │  ├─ main.py
│  │  │  ├─ api/
│  │  │  ├─ core/
│  │  │  ├─ repositories/
│  │  │  ├─ schemas/
│  │  │  ├─ src/
│  │  │  └─ workers/
│  │  └─ tests/
│  │     ├─ unit/
│  │     ├─ api/
│  │     ├─ integration/
│  │     └─ contract/
│  └─ graph/                       # graph projector service
│     ├─ Dockerfile
│     ├─ pyproject.toml
│     ├─ app/
│     │  ├─ main.py
│     │  ├─ checkpoints/
│     │  ├─ consumers/
│     │  ├─ mappers/
│     │  └─ neo4j/
│     └─ tests/
│        ├─ unit/
│        └─ integration/
├─ tests/                          # repository-level tests
│  ├─ e2e/
│  ├─ integration/
│  │  ├─ conftest.py
│  │  └─ docker-compose.test.yml
│  └─ contract/
├─ pyproject.toml
└─ uv.lock
```

## Web Domain Apps (`src/web/apps`)

- `base`: authentication, permissions, shared API endpoints, health endpoint.
- `projects`: main project domain (models, serializers, validators, viewsets).
- `applications`: application workflow domain (currently scaffold/basic files).
- `search`: search endpoints/domain.
- `tags`: tags domain scaffold.
- `imports`: import pipeline scaffold.
- `outbox`: outbox domain scaffold.
- `api`: top-level DRF API wiring.

## Notes vs Target Architecture

- `src/graph/` is already present as a separate service; naming can be aligned later to `src/graph_projector/` if needed.
- `contracts/` directory is not created yet (OpenAPI/events source-of-truth still pending as a separate step).
- `docs/architecture`, `docs/data`, `docs/events`, `docs/openapi`, `docs/security` are not yet split into dedicated folders.
- `infra/docker-compose.test.yml` currently lives in `tests/integration/docker-compose.test.yml`.
