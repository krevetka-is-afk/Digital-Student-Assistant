from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CI_WORKFLOW_PATH = ROOT_DIR / '.github' / 'workflows' / 'ci.yml'
STAGING_COMPOSE_PATH = ROOT_DIR / 'infra' / 'docker-compose.staging.yml'
STAGING_ENV_PATH = ROOT_DIR / 'infra' / '.env.staging.example'


def test_staging_compose_is_full_stack():
    compose = STAGING_COMPOSE_PATH.read_text(encoding='utf-8')

    assert '\n  web:\n' in compose
    assert '\n  postgres:\n' in compose
    assert '\n  nginx:\n' in compose
    assert '\n  ml:\n' in compose
    assert '\n  graph:\n' in compose
    assert '\n  neo4j:\n' in compose
    assert 'ML_SERVICE_URL: ${ML_SERVICE_URL:-http://ml:8000}' in compose
    assert 'postgres-staging' in compose
    assert 'neo4j-staging' in compose
    assert 'bootstrap-state-staging' in compose
    neo4j_block = compose.split('\n  neo4j:\n', 1)[1].split('\n  web:\n', 1)[0]
    assert 'env_file:' not in neo4j_block


def test_staging_workflow_uses_staging_specific_artifacts():
    workflow = CI_WORKFLOW_PATH.read_text(encoding='utf-8')

    assert 'infra/docker-compose.staging.yml' in workflow
    assert 'infra/.env.staging' in workflow
    assert 'pull web ml graph' in workflow
    assert 'infra/docker-compose.prod.yml \
        --env-file infra/.env.prod pull web ml graph' not in workflow
    assert 'replace_if_placeholder "DJANGO_SECRET_KEY"' in workflow
    assert 'replace_if_placeholder "NEO4J_AUTH"' in workflow
    assert 'Staging deploy failed; collecting docker compose diagnostics...' in workflow
    assert 'STAGING_BASE_URL=' in workflow
    assert 'STAGING_URL_RAW=' in workflow
    assert 'STAGING_SCHEME=' in workflow
    assert 'DJANGO_CSRF_TRUSTED_ORIGINS' in workflow
    allowed_hosts_line = (
        'set_env_key "DJANGO_ALLOWED_HOSTS" "${STAGING_HOST},localhost,127.0.0.1,web"'
    )
    assert allowed_hosts_line in workflow
    assert 'set_env_key "DJANGO_SECURE_SSL_REDIRECT" "true"' in workflow
    assert 'set_env_key "DJANGO_SECURE_SSL_REDIRECT" "false"' in workflow
    assert 'server_name ${STAGING_HOST};' in workflow
    assert 'ssl_certificate /etc/letsencrypt/live/${STAGING_HOST}/fullchain.pem;' in workflow
    assert 'sudo -n test -r "/etc/letsencrypt/live/${STAGING_HOST}/fullchain.pem"' in workflow
    assert 'Missing TLS certificate for ${STAGING_HOST}' in workflow
    assert 'restart nginx' in workflow
    assert 'PUBLIC_CURL_OPTS=' in workflow
    assert 'base_url="${STAGING_URL%/}"' in workflow
    assert '"$base_url/api/v1/ready/"' in workflow
    assert 'staging\\.example' in workflow
    assert '--force-recreate --wait --wait-timeout 240' in workflow
    assert 'require_stable_env_for_existing_volume' in workflow
    assert '"infra_postgres-staging"' in workflow
    assert '"infra_neo4j-staging"' in workflow
    assert 'Refusing to generate a new credential' in workflow


def test_staging_env_example_exists_for_full_stack():
    env_example = STAGING_ENV_PATH.read_text(encoding='utf-8')

    assert 'ML_SERVICE_URL=http://ml:8000' in env_example
    assert 'NEO4J_AUTH=' in env_example
    assert 'ML_ENABLE_BACKGROUND_POLLER=false' in env_example
    assert 'GRAPH_ENABLE_BACKGROUND_POLLER=false' in env_example
