import json
import os
import sys
from pathlib import Path

import django
from django.conf import settings
from django.test import Client
from django.urls import reverse

ROOT_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT_DIR / "src" / "web"
APPS_DIR = WEB_DIR / "apps"
API_CONTRACT_PATH = ROOT_DIR / "docs" / "architecture" / "contracts" / "api_contract.json"

for path in (WEB_DIR, APPS_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append("testserver")


def _load_api_contract() -> dict:
    return json.loads(API_CONTRACT_PATH.read_text(encoding="utf-8"))


def _load_generated_openapi() -> dict:
    client = Client()
    response = client.get(reverse("api-schema"), HTTP_ACCEPT="application/vnd.oai.openapi+json")

    assert response.status_code == 200
    return response.json()


def test_api_contract_required_paths_are_present_in_generated_openapi():
    contract = _load_api_contract()
    generated_schema = _load_generated_openapi()

    required_paths = set(contract["required_paths"])
    required_operations = contract["required_operations"]
    actual_paths = set(generated_schema["paths"].keys())

    assert required_paths
    assert required_paths == set(required_operations)
    assert required_paths.issubset(actual_paths)


def test_api_contract_required_operations_are_present_in_generated_openapi():
    contract = _load_api_contract()
    generated_schema = _load_generated_openapi()

    for path, methods in contract["required_operations"].items():
        actual_methods = set(generated_schema["paths"][path].keys())
        assert set(methods).issubset(actual_methods)


def test_api_contract_required_schema_components_are_present_in_generated_openapi():
    contract = _load_api_contract()
    generated_schema = _load_generated_openapi()

    required_schemas = set(contract["required_schema_components"])
    actual_schemas = set(generated_schema.get("components", {}).get("schemas", {}).keys())

    assert required_schemas
    assert required_schemas.issubset(actual_schemas)
