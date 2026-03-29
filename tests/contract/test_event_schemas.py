import ast
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT_DIR / "docs" / "architecture" / "contracts" / "event_contract.json"
WEB_APPS_DIR = ROOT_DIR / "src" / "web" / "apps"


def _load_event_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _collect_emitted_event_types() -> set[str]:
    event_types: set[str] = set()

    for path in WEB_APPS_DIR.rglob("*.py"):
        if "migrations" in path.parts:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "emit_event":
                continue

            for keyword in node.keywords:
                if keyword.arg != "event_type":
                    continue
                if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    event_types.add(keyword.value.value)

    return event_types


def test_event_contract_matches_current_emitters():
    payload = _load_event_contract()

    assert set(payload["required_event_types"]) == _collect_emitted_event_types()
