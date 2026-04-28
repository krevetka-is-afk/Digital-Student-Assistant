#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
environment="${DSA_ENVIRONMENT:-prod}"
compose_file="${DSA_COMPOSE_FILE:-infra/docker-compose.${environment}.yml}"
env_file="${DSA_ENV_FILE:-infra/.env.${environment}}"
backup_root="${DSA_BACKUP_DIR:-/var/backups/dsa/${environment}}"
retention_days="${DSA_BACKUP_RETENTION_DAYS:-14}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="${backup_root}/${timestamp}"

cd "$repo_dir"

if [[ ! -f "$compose_file" ]]; then
  echo "Compose file not found: $compose_file" >&2
  exit 1
fi

if [[ ! -f "$env_file" ]]; then
  echo "Environment file not found: $env_file" >&2
  exit 1
fi

mkdir -p "$run_dir"
chmod 700 "$backup_root" "$run_dir"

postgres_dump="${run_dir}/postgres.sql.gz"

docker compose -f "$compose_file" --env-file "$env_file" exec -T postgres \
  sh -ec 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip -9 > "$postgres_dump"

sha256sum "$postgres_dump" > "${postgres_dump}.sha256"

cat > "${run_dir}/manifest.txt" <<EOF
environment=${environment}
created_at_utc=${timestamp}
compose_file=${compose_file}
env_file=${env_file}
postgres_dump=$(basename "$postgres_dump")
retention_days=${retention_days}
EOF

find "$backup_root" \
  -mindepth 1 \
  -maxdepth 1 \
  -type d \
  -mtime "+${retention_days}" \
  -exec rm -rf {} +

echo "Backup written to ${run_dir}"
