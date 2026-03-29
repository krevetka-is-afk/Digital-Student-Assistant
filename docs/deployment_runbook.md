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

## Post-Deploy Load Test Plan

After the first stable server deployment, run a dedicated load-test stage before deciding whether
`web`, `ml`, and `graph` must be split across different machines.

Goals:

- measure whether the current single-host topology survives realistic peak traffic;
- identify whether the bottleneck is CPU, RAM, database I/O, or the ML/graph sidecars;
- decide from measurements, not assumptions, whether ML must move to a separate host.

Minimum scenarios to execute:

1. catalog browsing load on `GET /api/v1/projects/` and `GET /api/v1/search/`;
2. personal-cabinet load on `GET /api/v1/account/student/overview/` and customer/CPPRP list views;
3. recommendation load on `GET /api/v1/recs/search/` and `GET /api/v1/recs/recommendations/`;
4. write workflow load on project/application submit-review paths;
5. downstream synchronization pressure via `GET /api/v1/outbox/events/` while import/review traffic is active.

Record during the run:

- p50/p95/p99 latency per critical endpoint;
- host CPU, RAM, disk I/O, and DB saturation;
- separate resource pressure for `web`, `ml`, and `graph` containers;
- backlog/lag for outbox consumers and recommendation freshness.

Decision rule:

- keep single-host deployment if peak traffic stays within latency/error budgets with safe headroom;
- move `ml` first to a separate machine if recommendation/search load becomes the dominant bottleneck;
- consider splitting `graph` only if projector lag or graph-side resource use becomes operationally significant.
