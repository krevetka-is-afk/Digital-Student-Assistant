import importlib.util
from pathlib import Path

import pytest
from starlette.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[1]
MAIN_FILE = SERVICE_ROOT / "app" / "main.py"


def _load_app():
    spec = importlib.util.spec_from_file_location("ml_test_main", MAIN_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load ML app from {MAIN_FILE}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


app = _load_app()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
