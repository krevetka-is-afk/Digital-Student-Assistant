# Create your tests here.
from django.test import Client
from django.urls import reverse


def test_health_custom_ok():
    c = Client()
    r = c.get(reverse("health_custom"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "web"}
