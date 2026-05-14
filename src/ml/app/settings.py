from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MLSettings:
    outbox_base_url: str
    outbox_consumer: str
    outbox_auth_header: str
    outbox_timeout_sec: float
    default_batch_size: int
    poll_interval_sec: float
    enable_background_poller: bool
    index_state_path: str



def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _auth_header_from_env(*, header_env: str, token_env: str) -> str:
    specific_header = os.getenv(header_env, "").strip()
    if specific_header:
        return specific_header

    specific_token = os.getenv(token_env, "").strip()
    if specific_token:
        return f"Bearer {specific_token}"

    return os.getenv("OUTBOX_AUTH_HEADER", "").strip()



def load_settings() -> MLSettings:
    settings = MLSettings(
        outbox_base_url=os.getenv("OUTBOX_BASE_URL", "http://web:8000").rstrip("/"),
        outbox_consumer=os.getenv("OUTBOX_CONSUMER", "ml").strip() or "ml",
        outbox_auth_header=_auth_header_from_env(
            header_env="ML_OUTBOX_AUTH_HEADER",
            token_env="ML_OUTBOX_SERVICE_TOKEN",
        ),
        outbox_timeout_sec=float(os.getenv("OUTBOX_TIMEOUT_SEC", "10")),
        default_batch_size=max(1, int(os.getenv("OUTBOX_BATCH_SIZE", "100"))),
        poll_interval_sec=max(0.5, float(os.getenv("OUTBOX_POLL_INTERVAL_SEC", "5"))),
        enable_background_poller=_parse_bool(
            os.getenv("ML_ENABLE_BACKGROUND_POLLER"), default=False
        ),
        index_state_path=os.getenv("ML_INDEX_STATE_PATH", "/app/data/ml-index.json").strip()
        or "/app/data/ml-index.json",
    )
    if settings.enable_background_poller and not settings.outbox_auth_header:
        raise ValueError("OUTBOX_AUTH_HEADER is required when ML_ENABLE_BACKGROUND_POLLER=true.")
    return settings
