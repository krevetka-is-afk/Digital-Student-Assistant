# Deployment Runbook

## Services

- `postgres`: operational data store
- `web`: Django + DRF backend
- `ml`: recommendation/search gateway
- `graph`: graph projector
- `nginx`: reverse proxy and public entrypoint

## Prerequisites (clean machine)

- Docker Engine 24+ with Compose plugin
- `curl`
- `openssl`

## GitHub Actions CD (production)

Workflow file: `.github/workflows/deploy-prod.yml` (manual trigger via `workflow_dispatch`).

Required GitHub Environment (`production`) secrets:

- `PROD_SSH_HOST`
- `PROD_SSH_PORT`
- `PROD_SSH_USER`
- `PROD_SSH_KEY`
- `PROD_APP_DIR`

How to run:

1. Open GitHub Actions -> `Deploy Production`.
2. Click `Run workflow`.
3. Set `ref` (for example `main` or release tag).
4. Wait for deploy + smoke suite completion.

## Production env bootstrap

```bash
cp infra/.env.prod.example infra/.env.prod
chmod 600 infra/.env.prod
```

Generate a strong Django secret before the first deploy:

```bash
python - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
```

Put the generated value into `DJANGO_SECRET_KEY` in `infra/.env.prod`.
If your platform provides mounted secrets, use `DJANGO_SECRET_KEY_FILE` and `DATABASE_URL_FILE`
instead of inline secret values.

## First deploy

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod pull
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod build
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d
```

After startup, verify service health:

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod ps
```

## Smoke suite

Run the scripted smoke checks:

```bash
scripts/smoke-prod.sh
```

Optional explicit invocation:

```bash
ENV_FILE=infra/.env.prod COMPOSE_FILE=infra/docker-compose.prod.yml scripts/smoke-prod.sh
```

Tuning retries for slower cold starts:

```bash
SMOKE_RETRY_COUNT=30 SMOKE_RETRY_DELAY_SEC=4 scripts/smoke-prod.sh
```

The suite validates:

- external health/readiness via nginx (`/api/v1/health/`, `/api/v1/ready/`)
- API baseline response (`/api/v1/projects/`)
- internal readiness for `ml` and `graph`

## Observability quick checks

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod ps
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod logs --since=10m web nginx ml graph
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod top
```

Operator signals to watch during rollout:

- `web` readiness stays `healthy` and serves `/api/v1/ready/` without spikes of `503`.
- `nginx` error log has no repeated upstream connection/reset errors.
- `graph` readiness reports `status=ok` and checkpoint movement after event activity.

## Backup and restore

```bash
scripts/backup-postgres.sh ./backups
scripts/restore-postgres.sh ./backups/postgres-YYYYMMDD-HHMMSS.sql
```

## Release rehearsal checklist

1. Create a DB backup: `scripts/backup-postgres.sh ./backups`.
2. Start candidate release: `docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d --build`.
3. Confirm all services are healthy: `docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod ps`.
4. Run smoke suite: `scripts/smoke-prod.sh`.
5. Execute critical user flow: import EPP, publish project, submit application, moderation path.
6. Verify integration endpoints: `/api/v1/outbox/events/`, `/api/v1/recs/search/`, `/api/v1/recs/recommendations/`, graph `/state`.
7. Record release result with timestamp and git SHA.

## Rollback notes

If smoke checks or critical flows fail:

1. Stop rollout traffic (keep nginx up, stop app services if needed).
2. Revert image/tag or branch to previous known-good release.
3. Restart stack: `docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d`.
4. If schema/data changes are incompatible, restore DB backup:
   `scripts/restore-postgres.sh ./backups/<last-good-backup>.sql`.
5. Re-run `scripts/smoke-prod.sh` to confirm recovered baseline.

Note on HTTPS redirect:

- `DJANGO_SECURE_SSL_REDIRECT=false` is the safe default for this plain HTTP compose topology.
- Set it to `true` only when TLS is terminated at ingress/LB and `X-Forwarded-Proto: https` is
  preserved end-to-end.

## Post-deploy load test plan

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
