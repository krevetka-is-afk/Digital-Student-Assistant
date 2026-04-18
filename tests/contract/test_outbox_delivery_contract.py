import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
API_CONTRACT_PATH = ROOT_DIR / "docs" / "architecture" / "contracts" / "api_contract.json"
OUTBOX_DELIVERY_CONTRACT_PATH = (
    ROOT_DIR / "docs" / "architecture" / "contracts" / "outbox_delivery_contract.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_outbox_delivery_contract_is_aligned_with_api_contract():
    api_contract = _load_json(API_CONTRACT_PATH)
    outbox_delivery_contract = _load_json(OUTBOX_DELIVERY_CONTRACT_PATH)

    required_paths = set(api_contract["required_paths"])
    assert outbox_delivery_contract["poll_endpoint"] in required_paths
    assert outbox_delivery_contract["ack_endpoint"] in required_paths
    assert outbox_delivery_contract["checkpoint_endpoint_template"] in required_paths


def test_outbox_delivery_contract_defines_ml_and_graph_consumer_rules():
    outbox_delivery_contract = _load_json(OUTBOX_DELIVERY_CONTRACT_PATH)

    consumers = outbox_delivery_contract["consumers"]
    assert {"ml", "graph"}.issubset(consumers)
    for consumer in ("ml", "graph"):
        assert "resume" in consumers[consumer]
        assert "replay" in consumers[consumer]
        assert "idempotency_rule" in consumers[consumer]
