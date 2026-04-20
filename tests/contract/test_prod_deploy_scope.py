from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DEPLOY_WORKFLOW_PATH = ROOT_DIR / '.github' / 'workflows' / 'deploy-prod.yml'
PROD_COMPOSE_PATH = ROOT_DIR / 'infra' / 'docker-compose.prod.yml'
SMOKE_SCRIPT_PATH = ROOT_DIR / 'scripts' / 'smoke-prod.sh'


def test_prod_compose_is_web_only():
    compose = PROD_COMPOSE_PATH.read_text(encoding='utf-8')

    assert '\n  web:\n' in compose
    assert '\n  postgres:\n' in compose
    assert '\n  nginx:\n' in compose
    assert '\n  ml:\n' not in compose
    assert '\n  graph:\n' not in compose
    assert '\n  neo4j:\n' not in compose
    assert 'ML_SERVICE_URL: ${ML_SERVICE_URL:-}' in compose
    assert 'depends_on:\n      postgres:' in compose
    assert 'graph-prod' not in compose
    assert 'neo4j-prod' not in compose


def test_prod_workflow_only_builds_and_pulls_web_image():
    workflow = DEPLOY_WORKFLOW_PATH.read_text(encoding='utf-8')

    assert 'Build and push web image' in workflow
    assert 'Build and push ml image' not in workflow
    assert 'Build and push graph image' not in workflow
    assert '"${compose_cmd[@]}" pull web' in workflow
    assert 'pull web ml graph' not in workflow
    assert 'for service in postgres web nginx; do' in workflow


def test_prod_smoke_script_skips_internal_ml_and_graph_checks():
    smoke = SMOKE_SCRIPT_PATH.read_text(encoding='utf-8')

    assert '/api/v1/health/' in smoke
    assert '/api/v1/ready/' in smoke
    assert '/api/v1/projects/' in smoke
    assert 'http://ml:8000/ready' not in smoke
    assert 'http://graph:8002/ready' not in smoke
