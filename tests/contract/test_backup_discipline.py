from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT_PATH = ROOT_DIR / 'scripts' / 'backup-stack.sh'
INSTALL_SCRIPT_PATH = ROOT_DIR / 'scripts' / 'install-backup-timer.sh'
RESTORE_SCRIPT_PATH = ROOT_DIR / 'scripts' / 'restore-postgres.sh'


def test_backup_script_creates_compressed_postgres_dump_with_retention():
    script = BACKUP_SCRIPT_PATH.read_text(encoding='utf-8')

    assert 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' in script
    assert '| gzip -9 > "$postgres_dump"' in script
    assert 'sha256sum "$postgres_dump"' in script
    assert 'DSA_BACKUP_RETENTION_DAYS:-14' in script
    assert 'find "$backup_root"' in script
    assert '--env-file "$env_file"' in script


def test_backup_timer_installer_runs_nightly_with_persistent_catchup():
    script = INSTALL_SCRIPT_PATH.read_text(encoding='utf-8')

    assert 'DSA_BACKUP_ON_CALENDAR:-*-*-* 03:20:00' in script
    assert 'Persistent=true' in script
    assert 'RandomizedDelaySec=10m' in script
    assert 'ExecStart=${repo_dir}/scripts/backup-stack.sh' in script
    assert 'systemctl enable --now "$timer_name"' in script


def test_restore_script_accepts_compressed_backups_and_env_specific_compose():
    script = RESTORE_SCRIPT_PATH.read_text(encoding='utf-8')

    assert 'backup.sql|backup.sql.gz' in script
    assert 'gzip -dc "$backup_file"' in script
    assert 'infra/docker-compose.${environment}.yml' in script
    assert '--env-file "$env_file"' in script
