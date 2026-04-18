#!/usr/bin/env bash
set -euo pipefail

backup_dir="${1:-./backups}"
timestamp="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"

docker compose -f infra/docker-compose.prod.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-dsa}" "${POSTGRES_DB:-dsa}" \
  > "${backup_dir}/postgres-${timestamp}.sql"

echo "Backup written to ${backup_dir}/postgres-${timestamp}.sql"
