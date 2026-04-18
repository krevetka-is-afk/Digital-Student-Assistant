#!/usr/bin/env bash
set -euo pipefail

VM_HOST="${VM_HOST:-}"
VM_USER="${VM_USER:-deploy}"
SSH_PORT="${SSH_PORT:-22}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/dsa}"
REMOTE_DIR="${REMOTE_DIR:-/opt/dsa}"
PORT_MAPPING="${PORT_MAPPING:-8080:80}"
PUBLIC_HOST="${PUBLIC_HOST:-}"
RUN_SMOKE="${RUN_SMOKE:-1}"

usage() {
  cat <<'EOF'
Usage:
  scripts/upload-and-deploy-vm.sh <vm_host>

Environment variables:
  VM_HOST      VM IP or domain (required if no positional arg)
  VM_USER      SSH user (default: deploy)
  SSH_PORT     SSH port (default: 22)
  SSH_KEY      SSH private key path (default: ~/.ssh/dsa)
  REMOTE_DIR   Remote project directory (default: /opt/dsa)
  PORT_MAPPING Nginx port mapping host:container (default: 8080:80)
  PUBLIC_HOST  Public host/IP for ALLOWED_HOSTS/CSRF (default: VM_HOST)
  RUN_SMOKE    1 to run smoke checks, 0 to skip (default: 1)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "$VM_HOST" && -n "${1:-}" ]]; then
  VM_HOST="$1"
fi

if [[ -z "$VM_HOST" ]]; then
  echo "VM_HOST is required." >&2
  usage
  exit 1
fi

if [[ -z "$PUBLIC_HOST" ]]; then
  PUBLIC_HOST="$VM_HOST"
fi

if [[ ! -f "$SSH_KEY" ]]; then
  echo "SSH key not found: $SSH_KEY" >&2
  exit 1
fi

SSH_OPTS=(-i "$SSH_KEY" -p "$SSH_PORT" -o StrictHostKeyChecking=accept-new)
REMOTE="${VM_USER}@${VM_HOST}"

echo "Uploading project to ${REMOTE}:${REMOTE_DIR} ..."

COPYFILE_DISABLE=1 tar --format ustar \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.DS_Store' \
  --exclude='._*' \
  --exclude='.idea' \
  --exclude='.tmp' \
  --exclude='.pytest_cache' \
  --exclude='.ruff_cache' \
  -czf - . \
  | ssh "${SSH_OPTS[@]}" "$REMOTE" "set -euo pipefail
      sudo mkdir -p '$REMOTE_DIR'
      sudo chown -R '$VM_USER':'$VM_USER' '$REMOTE_DIR'
      if [ -f '$REMOTE_DIR/infra/.env.prod' ]; then
        cp '$REMOTE_DIR/infra/.env.prod' /tmp/dsa.env.prod.backup.\$\$
      fi
      rm -rf '$REMOTE_DIR'/*
      tar -xzf - -C '$REMOTE_DIR'
      if [ -f /tmp/dsa.env.prod.backup.\$\$ ]; then
        mv /tmp/dsa.env.prod.backup.\$\$ '$REMOTE_DIR/infra/.env.prod'
        chmod 600 '$REMOTE_DIR/infra/.env.prod'
      fi
    "

echo "Running remote deploy ..."

ssh "${SSH_OPTS[@]}" "$REMOTE" "set -euo pipefail
  cd '$REMOTE_DIR'
  APP_DIR='$REMOTE_DIR' \
  PORT_MAPPING='$PORT_MAPPING' \
  PUBLIC_HOST='$PUBLIC_HOST' \
  RUN_SMOKE='$RUN_SMOKE' \
  bash '$REMOTE_DIR/scripts/deploy-prod-vm.sh'
"

echo "Done."
