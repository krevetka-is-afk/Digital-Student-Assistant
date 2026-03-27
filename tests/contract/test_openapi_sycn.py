import json
from pathlib import Path


def test_api_contract_declares_release_paths():
    contract_path = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "api_contract.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8"))

    assert {
        "/api/v1/projects/",
        "/api/v1/applications/",
        "/api/v1/users/me/favorites/",
        "/api/v1/recs/search/",
        "/api/v1/recs/recommendations/",
        "/api/v1/imports/epp/",
        "/api/v1/outbox/events/",
    }.issubset(set(payload["required_paths"]))
