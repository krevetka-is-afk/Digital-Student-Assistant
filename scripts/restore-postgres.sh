#!/usr/bin/env bash
set -euo pipefail

backup_file="${1:?Usage: scripts/restore-postgres.sh <backup.sql|backup.sql.gz>}"
environment="${DSA_ENVIRONMENT:-prod}"
compose_file="${DSA_COMPOSE_FILE:-infra/docker-compose.${environment}.yml}"
env_file="${DSA_ENV_FILE:-infra/.env.${environment}}"

if [[ "$backup_file" == *.gz ]]; then
  gzip -dc "$backup_file" | docker compose -f "$compose_file" --env-file "$env_file" \
    exec -T postgres sh -ec 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
else
  docker compose -f "$compose_file" --env-file "$env_file" \
    exec -T postgres sh -ec 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"' < "$backup_file"
fi

echo "Restore completed from $backup_file"
