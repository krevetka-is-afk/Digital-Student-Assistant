#!/usr/bin/env bash
set -euo pipefail

backup_file="${1:?Usage: scripts/restore-postgres.sh <backup.sql>}"

docker compose -f infra/docker-compose.prod.yml exec -T postgres \
  psql -U "${POSTGRES_USER:-dsa}" "${POSTGRES_DB:-dsa}" < "$backup_file"

echo "Restore completed from $backup_file"
