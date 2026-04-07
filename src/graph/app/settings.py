from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GraphSettings:
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    outbox_base_url: str
    outbox_consumer: str
    outbox_auth_header: str
    outbox_timeout_sec: float
    default_batch_size: int
    poll_interval_sec: float
    enable_background_poller: bool



def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}



def load_settings() -> GraphSettings:
    settings = GraphSettings(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "test"),
        outbox_base_url=os.getenv("OUTBOX_BASE_URL", "http://web:8000").rstrip("/"),
        outbox_consumer=os.getenv("OUTBOX_CONSUMER", "graph").strip() or "graph",
        outbox_auth_header=os.getenv("OUTBOX_AUTH_HEADER", ""),
        outbox_timeout_sec=float(os.getenv("OUTBOX_TIMEOUT_SEC", "10")),
        default_batch_size=max(1, int(os.getenv("OUTBOX_BATCH_SIZE", "100"))),
        poll_interval_sec=max(0.5, float(os.getenv("OUTBOX_POLL_INTERVAL_SEC", "5"))),
        enable_background_poller=_parse_bool(
            os.getenv("GRAPH_ENABLE_BACKGROUND_POLLER"), default=False
        ),
    )
    if settings.enable_background_poller and not settings.outbox_auth_header:
        raise ValueError("OUTBOX_AUTH_HEADER is required when GRAPH_ENABLE_BACKGROUND_POLLER=true.")
    return settings
