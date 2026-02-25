# Project Structure

```txt
Digital-Student-Assistant/
├─ README.md
├─ .env.example
├─ .github/
│  └─ workflows/                 # CI: lint/test/build
├─ docs/
│  ├─ adr/                       # ADR-001, ADR-002...
│  ├─ architecture/              # diagrams, C4, sequence
│  └─ api/                       # exported OpenAPI schemas (optional)
├─ infra/
│  ├─ docker-compose.yml
│  ├─ nginx/                     # optional reverse proxy
│  └─ postgres/                  # init scripts, backups
├─ scripts/
│  ├─ seed_db.py
│  ├─ import_projects_xlsx.py
│  └─ dev_reset.sh
└─ services/
   ├─ web/                       # Django modular monolith (SSR + DRF)
   │  ├─ pyproject.toml
   │  ├─ manage.py
   │  ├─ config/                 # Django project package
   │  │  ├─ settings/
   │  │  │  ├─ base.py
   │  │  │  ├─ dev.py
   │  │  │  └─ prod.py
   │  │  ├─ urls.py
   │  │  ├─ asgi.py
   │  │  ├─ wsgi.py
   │  │  └─ celery_app.py         # Celery config lives with Django
   │  ├─ apps/                    # domain modules (bounded contexts)
   │  │  ├─ users/
   │  │  ├─ projects/
   │  │  ├─ applications/
   │  │  ├─ cpprp/
   │  │  ├─ integrations/         # sheets, LMS, SSO
   │  │  └─ recs/                 # facade client to ML service
   │  ├─ templates/               # project-level templates
   │  ├─ static/
   │  └─ tests/
   │
   └─ ml/                        # FastAPI ML service (embeddings/search/recs)
      ├─ pyproject.toml
      ├─ app/
      │  ├─ main.py
      │  ├─ api/
      │  │  ├─ v1/
      │  │  │  ├─ routes_embeddings.py
      │  │  │  ├─ routes_search.py
      │  │  │  └─ routes_recs.py
      │  │  └─ router.py
      │  ├─ core/                 # config, logging
      │  ├─ services/             # embedding, rerank, summarization
      │  ├─ repositories/         # pgvector queries, index persistence
      │  └─ schemas/              # pydantic DTOs
      └─ tests/
```

## DRF app structure (example for `projects` app):

Keep each domain as a Django app under apps/:
- apps/projects owns Project model + logic
- apps/applications owns workflow/status transitions
- apps/integrations owns Sheets/XLSX/LMS clients
- apps/recs is only a client facade to ML service

```txt
apps/projects/
├─ models.py
├─ services.py           # business logic (important boundary)
├─ selectors.py          # read/query functions
└─ api/
   ├─ serializers.py
   ├─ views.py (ViewSets)
   └─ urls.py / router.py
```
