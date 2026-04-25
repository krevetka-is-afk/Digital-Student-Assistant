# Create your tests here.
from django.test import Client
from django.urls import reverse


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


def test_api_docs_page_ok():
    c = Client()
    r = c.get(reverse("api-docs"))
    assert r.status_code == 200
    assert b"swagger" in r.content.lower()
