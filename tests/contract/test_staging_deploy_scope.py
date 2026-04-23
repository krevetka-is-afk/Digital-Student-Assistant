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


def test_staging_workflow_uses_staging_specific_artifacts():
    workflow = CI_WORKFLOW_PATH.read_text(encoding='utf-8')

    assert 'infra/docker-compose.staging.yml' in workflow
    assert 'infra/.env.staging' in workflow
    assert 'pull web ml graph' in workflow
    assert 'infra/docker-compose.prod.yml\
         --env-file infra/.env.prod pull web ml graph' not in workflow


def test_staging_env_example_exists_for_full_stack():
    env_example = STAGING_ENV_PATH.read_text(encoding='utf-8')

    assert 'ML_SERVICE_URL=http://ml:8000' in env_example
    assert 'NEO4J_AUTH=' in env_example
    assert 'ML_ENABLE_BACKGROUND_POLLER=false' in env_example
    assert 'GRAPH_ENABLE_BACKGROUND_POLLER=false' in env_example
