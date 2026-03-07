import pytest
from starlette.testclient import TestClient

try:
    # Works when pytest is started from services/ml
    from app.main import app
except ModuleNotFoundError:
    # Works when pytest is started from repo root
    from services.ml.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
