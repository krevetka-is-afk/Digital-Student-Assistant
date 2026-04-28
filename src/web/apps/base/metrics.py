from __future__ import annotations

from time import perf_counter

from django.http import HttpRequest, HttpResponse
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
    "dsa_web_http_requests_total",
    "Total HTTP requests handled by the web service.",
    ("method", "path", "status"),
    registry=REGISTRY,
)
HTTP_REQUEST_DURATION = Histogram(
    "dsa_web_http_request_duration_seconds",
    "HTTP request duration in seconds for the web service.",
    ("method", "path", "status"),
    registry=REGISTRY,
)
READINESS_STATUS = Gauge(
    "dsa_web_readiness_status",
    "Web readiness status by dependency check; 1 means healthy, 0 means degraded.",
    ("check",),
    registry=REGISTRY,
)


def metrics_response() -> HttpResponse:
    return HttpResponse(generate_latest(REGISTRY), content_type=CONTENT_TYPE_LATEST)


def set_readiness_check(*, check: str, healthy: bool) -> None:
    READINESS_STATUS.labels(check=check).set(1 if healthy else 0)


def route_label(request: HttpRequest) -> str:
    match = getattr(request, "resolver_match", None)
    route = getattr(match, "route", None)
    if route:
        return f"/{route.lstrip('/')}"
    return request.path_info or "unknown"


class PrometheusMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        started_at = perf_counter()
        try:
            response = self.get_response(request)
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
            status = str(getattr(response, "status_code", "unknown"))
            path = route_label(request)
            duration = perf_counter() - started_at
            HTTP_REQUESTS.labels(method=request.method, path=path, status=status).inc()
            HTTP_REQUEST_DURATION.labels(method=request.method, path=path, status=status).observe(
                duration
            )
            return response
