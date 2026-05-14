from apps.outbox.models import OutboxConsumerCheckpoint, OutboxEvent
from apps.projects.models import Project, ProjectStatus
from django.test import Client, override_settings
from django.urls import reverse


def _metric_value(content: str, metric_name: str, labels: str | None = None) -> float:
    prefix = metric_name if labels is None else f"{metric_name}{{{labels}}}"
    for line in content.splitlines():
        if line.startswith(f"{prefix} "):
            return float(line.rsplit(" ", 1)[1])
    raise AssertionError(f"Metric line not found: {prefix}")


def test_home_page_ok():
    c = Client()
    r = c.get(reverse("home"))
    assert r.status_code == 200
    assert b"Digital Student Assistant Web Service" in r.content


def test_health_root_ok():
    c = Client()
    r = c.get(reverse("health-root"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_root_ok():
    c = Client()
    r = c.get(reverse("ready-root"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "checks": {"database": "up"}}


def test_metrics_root_ok():
    c = Client()
    r = c.get(reverse("metrics-root"))
    assert r.status_code == 200
    assert "text/plain" in r["Content-Type"]
    assert b"dsa_web_http_requests_total" in r.content


def test_metrics_root_exposes_empty_outbox_domain_metrics():
    OutboxConsumerCheckpoint.objects.all().delete()
    OutboxEvent.objects.all().delete()
    c = Client()
    r = c.get(reverse("metrics-root"))

    content = r.content.decode()
    assert _metric_value(content, "dsa_web_outbox_latest_event_id") == 0
    assert _metric_value(content, "dsa_web_outbox_events_total") == 0
    assert _metric_value(content, "dsa_web_outbox_consumer_checkpoint", 'consumer="ml"') == 0
    assert _metric_value(content, "dsa_web_outbox_consumer_lag", 'consumer="graph"') == 0
    assert 'dsa_web_projects_total{status="draft"}' in content
    assert "dsa_web_faculty_persons_total" in content
    assert 'dsa_web_project_faculty_matches_total{status="candidate"}' in content


def test_metrics_root_exposes_outbox_lag_and_project_counts():
    OutboxConsumerCheckpoint.objects.all().delete()
    OutboxEvent.objects.all().delete()
    project = Project.objects.create(
        title="Metrics project",
        description="metrics",
        status=ProjectStatus.PUBLISHED,
    )
    latest_id = OutboxEvent.objects.order_by("-id").values_list("id", flat=True).first()
    assert latest_id is not None
    OutboxConsumerCheckpoint.objects.update_or_create(
        consumer="ml",
        defaults={"last_acked_event_id": latest_id},
    )
    OutboxConsumerCheckpoint.objects.update_or_create(
        consumer="graph",
        defaults={"last_acked_event_id": 0},
    )

    c = Client()
    r = c.get(reverse("metrics-root"))

    published_count = Project.objects.filter(status=ProjectStatus.PUBLISHED).count()
    content = r.content.decode()
    assert _metric_value(content, "dsa_web_outbox_latest_event_id") == latest_id
    assert _metric_value(content, "dsa_web_outbox_events_total") == OutboxEvent.objects.count()
    assert (
        _metric_value(content, "dsa_web_outbox_consumer_checkpoint", 'consumer="ml"')
        == latest_id
    )
    assert _metric_value(content, "dsa_web_outbox_consumer_lag", 'consumer="ml"') == 0
    assert _metric_value(content, "dsa_web_outbox_consumer_checkpoint", 'consumer="graph"') == 0
    assert _metric_value(content, "dsa_web_outbox_consumer_lag", 'consumer="graph"') == latest_id
    assert _metric_value(content, "dsa_web_projects_total", 'status="published"') == published_count
    assert project.pk is not None


@override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^metrics/$"])
def test_metrics_root_is_not_https_redirected_when_scraped_internally():
    c = Client()
    r = c.get(reverse("metrics-root"))
    assert r.status_code == 200
    assert "text/plain" in r["Content-Type"]


@override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^api/v1/outbox/"])
def test_outbox_api_is_not_https_redirected_for_internal_consumers():
    c = Client()
    r = c.get("/api/v1/outbox/consumers/ml/checkpoint/")
    assert r.status_code != 301


def test_api_v1_health_ok():
    c = Client()
    r = c.get(reverse("api-v1-health"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_api_v1_ready_ok():
    c = Client()
    r = c.get(reverse("api-v1-ready"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "checks": {"database": "up"}}


def test_api_v1_projects_list_ok():
    c = Client()
    r = c.get(reverse("api-v1-project-list"))
    assert r.status_code == 200


def test_api_root_ok():
    c = Client()
    r = c.get(reverse("api-index"))
    assert r.status_code == 200
    payload = r.json()
    assert payload["default_version"] == "v1"
    assert payload["versions"]["v1"].endswith("/api/v1/")
    assert payload["schema"].endswith("/api/schema/")
    assert payload["docs"].endswith("/api/docs/")
    assert "legacy" not in payload


def test_api_v1_root_ok():
    c = Client()
    r = c.get(reverse("api-v1-root"))
    assert r.status_code == 200
    payload = r.json()
    assert payload["version"] == "v1"
    assert payload["projects"].endswith("/api/v1/projects/")
    assert payload["initiative_proposals"].endswith("/api/v1/initiative-proposals/")
    assert payload["recs_search"].endswith("/api/v1/recs/search/")
    assert payload["imports_epp"].endswith("/api/v1/imports/epp/")


def test_api_schema_exposes_projects_query_params():
    c = Client()
    r = c.get(reverse("api-schema"), HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert r.status_code == 200

    payload = r.json()
    params = payload["paths"]["/api/v1/projects/"]["get"]["parameters"]
    param_names = {param["name"] for param in params}
    assert {
        "page",
        "page_size",
        "status",
        "q",
        "ordering",
        "source_type",
        "tech_tag",
        "education_program",
        "study_course",
        "work_format",
        "staffing_state",
        "application_state",
        "application_window_state",
        "is_team_project",
        "uses_ai",
    }.issubset(param_names)


def test_api_schema_exposes_initiative_proposal_paths():
    c = Client()
    r = c.get(reverse("api-schema"), HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert r.status_code == 200

    payload = r.json()
    assert "/api/v1/initiative-proposals/" in payload["paths"]
    assert "/api/v1/initiative-proposals/{id}/actions/submit/" in payload["paths"]
    assert "/api/v1/initiative-proposals/{id}/actions/moderate/" in payload["paths"]


def test_api_schema_exposes_auth_registration_and_email_token_paths():
    c = Client()
    r = c.get(reverse("api-schema"), HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert r.status_code == 200

    payload = r.json()
    paths = payload["paths"]
    assert "/api/v1/auth/register/" in paths
    assert "/api/v1/auth/verify-email/" in paths
    assert "/api/v1/auth/verify-email/resend/" in paths
    assert "/api/v1/auth/token/" in paths

    token_request_schema_ref = (
        paths["/api/v1/auth/token/"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    )
    schema_name = token_request_schema_ref["$ref"].rsplit("/", 1)[-1]
    token_request_schema = payload["components"]["schemas"][schema_name]
    token_properties = token_request_schema["properties"]
    assert "email" in token_properties
    assert "password" in token_properties
    assert "username" not in token_properties
    assert set(token_request_schema["required"]) == {"email", "password"}


def test_api_schema_hides_non_public_helper_routes():
    c = Client()
    r = c.get(reverse("api-schema"), HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert r.status_code == 200

    paths = set(r.json()["paths"])
    assert "/api/" in paths
    assert "/api/v1/" in paths
    assert "/api/schema/" not in paths
    assert "/base/" not in paths
    assert "/base/search" not in paths
    assert "/base/v2/projects/" not in paths
    assert "/health/" not in paths
    assert "/ready/" not in paths
    assert "/metrics/" not in paths


def test_api_docs_page_ok():
    c = Client()
    r = c.get(reverse("api-docs"))
    assert r.status_code == 200
    assert b"swagger" in r.content.lower()
