#!/usr/bin/env bash
set -euo pipefail

backup_dir="${1:-./backups}"

DSA_BACKUP_DIR="$backup_dir" \
DSA_BACKUP_RETENTION_DAYS="${DSA_BACKUP_RETENTION_DAYS:-3650}" \
DSA_ENVIRONMENT="${DSA_ENVIRONMENT:-prod}" \
  "$(dirname "${BASH_SOURCE[0]}")/backup-stack.sh"
