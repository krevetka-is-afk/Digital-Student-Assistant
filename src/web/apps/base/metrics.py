from __future__ import annotations

from time import perf_counter

from django.db.models import Count, Max
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
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
OUTBOX_LATEST_EVENT_ID = Gauge(
    "dsa_web_outbox_latest_event_id",
    "Latest web outbox event id.",
    registry=REGISTRY,
)
OUTBOX_EVENTS_TOTAL = Gauge(
    "dsa_web_outbox_events_total",
    "Total web outbox events stored.",
    registry=REGISTRY,
)
OUTBOX_CONSUMER_CHECKPOINT = Gauge(
    "dsa_web_outbox_consumer_checkpoint",
    "Last acknowledged web outbox event id by consumer.",
    ("consumer",),
    registry=REGISTRY,
)
OUTBOX_CONSUMER_LAG = Gauge(
    "dsa_web_outbox_consumer_lag",
    "Number of web outbox events pending acknowledgement by consumer.",
    ("consumer",),
    registry=REGISTRY,
)
OUTBOX_OLDEST_PENDING_AGE_SECONDS = Gauge(
    "dsa_web_outbox_oldest_pending_age_seconds",
    "Age in seconds of the oldest unacknowledged web outbox event by consumer.",
    ("consumer",),
    registry=REGISTRY,
)
PROJECTS_TOTAL = Gauge(
    "dsa_web_projects_total",
    "Total projects by status.",
    ("status",),
    registry=REGISTRY,
)
FACULTY_PERSONS_TOTAL = Gauge(
    "dsa_web_faculty_persons_total",
    "Total faculty persons.",
    registry=REGISTRY,
)
FACULTY_PUBLICATIONS_TOTAL = Gauge(
    "dsa_web_faculty_publications_total",
    "Total faculty publications.",
    registry=REGISTRY,
)
FACULTY_COURSES_TOTAL = Gauge(
    "dsa_web_faculty_courses_total",
    "Total faculty courses.",
    registry=REGISTRY,
)
PROJECT_FACULTY_MATCHES_TOTAL = Gauge(
    "dsa_web_project_faculty_matches_total",
    "Total project faculty matches by status.",
    ("status",),
    registry=REGISTRY,
)

OUTBOX_CONSUMERS = ("ml", "graph")


def metrics_response() -> HttpResponse:
    collect_domain_metrics()
    return HttpResponse(generate_latest(REGISTRY), content_type=CONTENT_TYPE_LATEST)


def set_readiness_check(*, check: str, healthy: bool) -> None:
    READINESS_STATUS.labels(check=check).set(1 if healthy else 0)


def collect_domain_metrics() -> None:
    from apps.faculty.models import (
        FacultyCourse,
        FacultyMatchStatus,
        FacultyPerson,
        FacultyPublication,
        ProjectFacultyMatch,
    )
    from apps.outbox.models import OutboxConsumerCheckpoint, OutboxEvent
    from apps.projects.models import Project, ProjectStatus

    outbox_stats = OutboxEvent.objects.aggregate(latest_id=Max("id"), total=Count("id"))
    latest_event_id = outbox_stats["latest_id"] or 0
    OUTBOX_LATEST_EVENT_ID.set(latest_event_id)
    OUTBOX_EVENTS_TOTAL.set(outbox_stats["total"] or 0)

    checkpoints = {
        checkpoint.consumer: checkpoint.last_acked_event_id
        for checkpoint in OutboxConsumerCheckpoint.objects.filter(consumer__in=OUTBOX_CONSUMERS)
    }
    now = timezone.now()
    for consumer in OUTBOX_CONSUMERS:
        checkpoint = checkpoints.get(consumer, 0)
        OUTBOX_CONSUMER_CHECKPOINT.labels(consumer=consumer).set(checkpoint)
        OUTBOX_CONSUMER_LAG.labels(consumer=consumer).set(max(latest_event_id - checkpoint, 0))
        oldest_pending = (
            OutboxEvent.objects.filter(id__gt=checkpoint).order_by("id").only("created_at").first()
        )
        oldest_pending_age = (
            max((now - oldest_pending.created_at).total_seconds(), 0) if oldest_pending else 0
        )
        OUTBOX_OLDEST_PENDING_AGE_SECONDS.labels(consumer=consumer).set(oldest_pending_age)

    project_counts = {
        row["status"]: row["total"]
        for row in Project.objects.values("status").annotate(total=Count("id"))
    }
    for status in ProjectStatus.values:
        PROJECTS_TOTAL.labels(status=status).set(project_counts.get(status, 0))

    FACULTY_PERSONS_TOTAL.set(FacultyPerson.objects.count())
    FACULTY_PUBLICATIONS_TOTAL.set(FacultyPublication.objects.count())
    FACULTY_COURSES_TOTAL.set(FacultyCourse.objects.count())

    match_counts = {
        row["status"]: row["total"]
        for row in ProjectFacultyMatch.objects.values("status").annotate(total=Count("id"))
    }
    for status in FacultyMatchStatus.values:
        PROJECT_FACULTY_MATCHES_TOTAL.labels(status=status).set(match_counts.get(status, 0))


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
