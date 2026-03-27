import pytest
from starlette.testclient import TestClient

try:
    from app.main import app
except ModuleNotFoundError:
    from src.graph.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
