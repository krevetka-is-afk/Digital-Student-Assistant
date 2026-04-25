import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.graph.app.main import create_app  # noqa: E402
from src.graph.app.settings import GraphSettings  # noqa: E402


@pytest.fixture
def app_factory():
    def _factory(*, graph_store, outbox_client):
        settings = GraphSettings(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="test",
            outbox_base_url="http://localhost:8000",
            outbox_consumer="graph",
            outbox_auth_header="",
            outbox_timeout_sec=1.0,
            default_batch_size=50,
            poll_interval_sec=0.5,
            enable_background_poller=False,
        )
        return create_app(
            settings=settings,
            graph_store=graph_store,
            outbox_client=outbox_client,
        )

    return _factory
