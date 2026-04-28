#!/usr/bin/env bash
set -euo pipefail

environment="${1:-prod}"
run_at="${DSA_BACKUP_ON_CALENDAR:-*-*-* 03:20:00}"
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="${DSA_BACKUP_DIR:-/var/backups/dsa/${environment}}"
retention_days="${DSA_BACKUP_RETENTION_DAYS:-14}"
service_name="dsa-backup-${environment}.service"
timer_name="dsa-backup-${environment}.timer"

if [[ "$environment" != "prod" && "$environment" != "staging" ]]; then
  echo "Usage: scripts/install-backup-timer.sh [prod|staging]" >&2
  exit 1
fi

sudo install -d -m 700 "$backup_dir"

sudo tee "/etc/systemd/system/${service_name}" >/dev/null <<EOF
[Unit]
Description=Digital Student Assistant ${environment} datastore backup
Wants=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=${repo_dir}
Environment=DSA_ENVIRONMENT=${environment}
Environment=DSA_BACKUP_DIR=${backup_dir}
Environment=DSA_BACKUP_RETENTION_DAYS=${retention_days}
ExecStart=${repo_dir}/scripts/backup-stack.sh
EOF

sudo tee "/etc/systemd/system/${timer_name}" >/dev/null <<EOF
[Unit]
Description=Run Digital Student Assistant ${environment} datastore backup nightly

[Timer]
OnCalendar=${run_at}
Persistent=true
RandomizedDelaySec=10m
Unit=${service_name}

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$timer_name"
sudo systemctl list-timers "$timer_name" --no-pager
