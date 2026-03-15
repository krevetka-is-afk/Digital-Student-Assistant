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


def test_api_v1_health_ok():
    c = Client()
    r = c.get(reverse("api-v1-health"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


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


def test_api_v1_root_ok():
    c = Client()
    r = c.get(reverse("api-v1-root"))
    assert r.status_code == 200
    payload = r.json()
    assert payload["version"] == "v1"
    assert payload["projects"].endswith("/api/v1/projects/")


def test_api_schema_exposes_projects_query_params():
    c = Client()
    r = c.get(reverse("api-schema"), HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert r.status_code == 200

    payload = r.json()
    params = payload["paths"]["/api/v1/projects/"]["get"]["parameters"]
    param_names = {param["name"] for param in params}
    assert {"page", "page_size", "status", "q", "ordering"}.issubset(param_names)


def test_api_docs_page_ok():
    c = Client()
    r = c.get(reverse("api-docs"))
    assert r.status_code == 200
    assert b"swagger" in r.content.lower()


def test_legacy_api_is_under_legacy_prefix():
    c = Client()
    r = c.get(reverse("legacy-api-root"))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_legacy_add_compat_alias_exists():
    c = Client()
    r = c.get(reverse("legacy-api-add-compat"))
    assert r.status_code == 405
