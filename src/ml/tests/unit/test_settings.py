import pytest

from src.ml.app.settings import load_settings


def _clear_outbox_env(monkeypatch):
    for name in (
        "OUTBOX_AUTH_HEADER",
        "ML_OUTBOX_AUTH_HEADER",
        "ML_OUTBOX_SERVICE_TOKEN",
        "ML_ENABLE_BACKGROUND_POLLER",
    ):
        monkeypatch.delenv(name, raising=False)


def test_ml_settings_builds_auth_header_from_service_token(monkeypatch):
    _clear_outbox_env(monkeypatch)
    monkeypatch.setenv("ML_ENABLE_BACKGROUND_POLLER", "true")
    monkeypatch.setenv("ML_OUTBOX_SERVICE_TOKEN", "ml-token")

    settings = load_settings()

    assert settings.enable_background_poller is True
    assert settings.outbox_auth_header == "Bearer ml-token"


def test_ml_settings_prefers_service_specific_header_over_shared_header(monkeypatch):
    _clear_outbox_env(monkeypatch)
    monkeypatch.setenv("OUTBOX_AUTH_HEADER", "Bearer shared-token")
    monkeypatch.setenv("ML_OUTBOX_AUTH_HEADER", "Bearer ml-token")

    settings = load_settings()

    assert settings.outbox_auth_header == "Bearer ml-token"


def test_ml_settings_requires_auth_when_background_poller_enabled(monkeypatch):
    _clear_outbox_env(monkeypatch)
    monkeypatch.setenv("ML_ENABLE_BACKGROUND_POLLER", "true")

    with pytest.raises(ValueError, match="OUTBOX_AUTH_HEADER is required"):
        load_settings()
