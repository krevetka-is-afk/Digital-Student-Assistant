# Deployment Runbook

## Services

- `postgres`: operational data store
- `web`: Django + DRF backend
- `ml`: recommendation/search stub gateway
- `graph`: graph projector stub with checkpoint persistence
- `nginx`: reverse proxy

## First Deploy

```bash
cp src/web/.env.example src/web/.env
cp src/ml/.env.example src/ml/.env
cp src/graph/.env.example src/graph/.env
docker compose -f infra/docker-compose.prod.yml up --build -d
```

## Smoke Checks

```bash
curl http://127.0.0.1/api/v1/health/
curl http://127.0.0.1/api/v1/recs/search/?q=graph
curl http://127.0.0.1:8001/ready
curl http://127.0.0.1:8002/state
```

## Backup And Restore

```bash
scripts/backup-postgres.sh ./backups
scripts/restore-postgres.sh ./backups/postgres-YYYYMMDD-HHMMSS.sql
```

## Release Rehearsal

1. Run migrations through `docker compose -f infra/docker-compose.prod.yml up`.
2. Import EPP through `/api/v1/imports/epp/`.
3. Publish project, submit application, review application.
4. Verify `outbox/events`, `recs/search`, `recs/recommendations`, `graph/state`.
