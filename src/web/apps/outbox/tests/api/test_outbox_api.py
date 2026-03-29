from uuid import uuid4

from apps.outbox.models import OutboxEvent
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def test_outbox_events_endpoint_returns_filtered_events():
    user = get_user_model().objects.create_user(
        username=f"cpprp-outbox-{uuid4().hex[:8]}",
        password="pass123456",
    )
    UserProfile.objects.create(user=user, role=UserRole.CPPRP)
    event = OutboxEvent.objects.create(
        event_type="project.changed",
        aggregate_type="project",
        aggregate_id="1",
        idempotency_key=f"project.changed:1:test:{uuid4().hex[:8]}",
        payload={"pk": 1},
    )

    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("api-v1-outbox-events"),
        data={"event_type": "project.changed", "since_id": event.id - 1},
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["results"]]
    assert event.id in ids
