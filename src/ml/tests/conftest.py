import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ml.app.main import create_app  # noqa: E402
from src.ml.app.settings import MLSettings  # noqa: E402


@pytest.fixture
def app_factory(tmp_path: Path):
    def _factory(*, index_store=None, outbox_client=None, enable_background_poller: bool = False):
        settings = MLSettings(
            outbox_base_url="http://localhost:8000",
            outbox_consumer="ml",
            outbox_auth_header="Bearer test-token",
            outbox_timeout_sec=1.0,
            default_batch_size=50,
            poll_interval_sec=0.5,
            enable_background_poller=enable_background_poller,
            index_state_path=str(tmp_path / "ml-index.json"),
        )
        return create_app(
            settings=settings,
            index_store=index_store,
            outbox_client=outbox_client,
        )

    return _factory


@pytest.fixture
def client(app_factory):
    app = app_factory()
    with TestClient(app) as c:
        yield c
