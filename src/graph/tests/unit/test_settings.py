import pytest

from src.graph.app.settings import load_settings


def _clear_outbox_env(monkeypatch):
    for name in (
        "OUTBOX_AUTH_HEADER",
        "GRAPH_OUTBOX_AUTH_HEADER",
        "GRAPH_OUTBOX_SERVICE_TOKEN",
        "GRAPH_ENABLE_BACKGROUND_POLLER",
    ):
        monkeypatch.delenv(name, raising=False)


def test_graph_settings_builds_auth_header_from_service_token(monkeypatch):
    _clear_outbox_env(monkeypatch)
    monkeypatch.setenv("GRAPH_ENABLE_BACKGROUND_POLLER", "true")
    monkeypatch.setenv("GRAPH_OUTBOX_SERVICE_TOKEN", "graph-token")

    settings = load_settings()

    assert settings.enable_background_poller is True
    assert settings.outbox_auth_header == "Bearer graph-token"


def test_graph_settings_prefers_service_specific_header_over_shared_header(monkeypatch):
    _clear_outbox_env(monkeypatch)
    monkeypatch.setenv("OUTBOX_AUTH_HEADER", "Bearer shared-token")
    monkeypatch.setenv("GRAPH_OUTBOX_AUTH_HEADER", "Bearer graph-token")

    settings = load_settings()

    assert settings.outbox_auth_header == "Bearer graph-token"


def test_graph_settings_requires_auth_when_background_poller_enabled(monkeypatch):
    _clear_outbox_env(monkeypatch)
    monkeypatch.setenv("GRAPH_ENABLE_BACKGROUND_POLLER", "true")

    with pytest.raises(ValueError, match="OUTBOX_AUTH_HEADER is required"):
        load_settings()
