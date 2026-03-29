import json
from pathlib import Path


def test_event_contract_declares_required_event_types():
    contract_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "architecture"
        / "contracts"
        / "event_contract.json"
    )
    payload = json.loads(contract_path.read_text(encoding="utf-8"))

    assert {
        "project.changed",
        "application.changed",
        "user_profile.changed",
        "deadline.changed",
        "import.completed",
        "recs.reindex_requested",
    }.issubset(set(payload["required_event_types"]))
