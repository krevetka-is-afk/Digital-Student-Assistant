from __future__ import annotations

from time import perf_counter
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "dsa_ml_http_requests_total",
    "Total HTTP requests handled by the ML service.",
    ("method", "path", "status"),
    registry=REGISTRY,
)
HTTP_REQUEST_DURATION = Histogram(
    "dsa_ml_http_request_duration_seconds",
    "HTTP request duration in seconds for the ML service.",
    ("method", "path", "status"),
    registry=REGISTRY,
)
READINESS_STATUS = Gauge(
    "dsa_ml_readiness_status",
    "ML readiness status by dependency check; 1 means healthy, 0 means degraded.",
    ("check",),
    registry=REGISTRY,
)
SYNC_REQUESTS = Counter(
    "dsa_ml_outbox_sync_requests_total",
    "Outbox sync attempts by mode and result for the ML service.",
    ("mode", "result"),
    registry=REGISTRY,
)
SYNC_EVENTS = Counter(
    "dsa_ml_outbox_sync_events_total",
    "Outbox events processed by the ML service.",
    ("mode",),
    registry=REGISTRY,
)
POLLER_CYCLES = Counter(
    "dsa_ml_poller_cycles_total",
    "Background poller cycles by result for the ML service.",
    ("result",),
    registry=REGISTRY,
)
PROJECTS_INDEXED = Gauge(
    "dsa_ml_projects_indexed",
    "Projects currently indexed by the ML service.",
    registry=REGISTRY,
)
PROFILES_INDEXED = Gauge(
    "dsa_ml_profiles_indexed",
    "Profiles currently indexed by the ML service.",
    registry=REGISTRY,
)
REINDEX_REQUESTS = Gauge(
    "dsa_ml_reindex_requests",
    "Reindex requests observed by the ML service.",
    registry=REGISTRY,
)
LAST_ACKED_EVENT_ID = Gauge(
    "dsa_ml_outbox_last_acked_event_id",
    "Last outbox event id mirrored by the ML service.",
    registry=REGISTRY,
)
LAST_EVENT_ID = Gauge(
    "dsa_ml_last_event_id",
    "Last event id observed by the ML service.",
    registry=REGISTRY,
)


def record_readiness(*, check: str, healthy: bool) -> None:
    READINESS_STATUS.labels(check=check).set(1 if healthy else 0)


def record_sync(*, mode: str, processed: int, success: bool) -> None:
    result = "success" if success else "error"
    SYNC_REQUESTS.labels(mode=mode, result=result).inc()
    if success:
        SYNC_EVENTS.labels(mode=mode).inc(processed)


def record_poller_cycle(*, success: bool) -> None:
    POLLER_CYCLES.labels(result="success" if success else "error").inc()


def update_state_metrics(summary: dict) -> None:
    PROJECTS_INDEXED.set(int(summary.get("projects_indexed") or 0))
    PROFILES_INDEXED.set(int(summary.get("profiles_indexed") or 0))
    REINDEX_REQUESTS.set(int(summary.get("reindex_requests") or 0))
    LAST_EVENT_ID.set(int(summary.get("last_event_id") or 0))
    checkpoint = summary.get("checkpoint_mirror") or {}
    LAST_ACKED_EVENT_ID.set(int(checkpoint.get("last_acked_event_id") or 0))


def route_label(request: Request) -> str:
    route = getattr(request.scope.get("route"), "path", None)
    return route or request.url.path


def add_metrics(
    app: FastAPI,
    *,
    collect_state_metrics: Callable[[Request], None] | None = None,
) -> None:
    @app.middleware("http")
    async def prometheus_metrics_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            status = "500"
            path = route_label(request)
            duration = perf_counter() - started_at
            HTTP_REQUESTS.labels(method=request.method, path=path, status=status).inc()
            HTTP_REQUEST_DURATION.labels(method=request.method, path=path, status=status).observe(
                duration
            )
            raise
        else:
            status = str(response.status_code)
            path = route_label(request)
            duration = perf_counter() - started_at
            HTTP_REQUESTS.labels(method=request.method, path=path, status=status).inc()
            HTTP_REQUEST_DURATION.labels(method=request.method, path=path, status=status).observe(
                duration
            )
            return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Response:
        if collect_state_metrics is not None:
            try:
                collect_state_metrics(request)
            except Exception:
                pass
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
