from uuid import uuid4

from apps.outbox.models import OutboxConsumerCheckpoint, OutboxEvent
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def _auth_client(role: str = UserRole.CPPRP) -> Client:
    user = get_user_model().objects.create_user(
        username=f"cpprp-outbox-{uuid4().hex[:8]}",
        password="placeholder",
    )
    UserProfile.objects.create(user=user, role=role)
    client = Client()
    client.force_login(user)
    return client


def test_outbox_events_endpoint_returns_filtered_events():
    client = _auth_client()
    event = OutboxEvent.objects.create(
        event_type="project.changed",
        aggregate_type="project",
        aggregate_id="1",
        idempotency_key=f"project.changed:1:test:{uuid4().hex[:8]}",
        payload={"pk": 1},
    )
    response = client.get(
        reverse("api-v1-outbox-events"),
        data={"event_type": "project.changed", "since_id": event.id - 1},
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["results"]]
    assert event.id in ids


def test_outbox_poll_mode_uses_consumer_checkpoint():
    client = _auth_client()
    consumer = f"graph-{uuid4().hex[:8]}"
    first = OutboxEvent.objects.create(
        event_type="project.changed",
        aggregate_type="project",
        aggregate_id="1",
        idempotency_key=f"project.changed:1:checkpoint:{uuid4().hex[:8]}",
        payload={"pk": 1},
    )
    second = OutboxEvent.objects.create(
        event_type="project.changed",
        aggregate_type="project",
        aggregate_id="2",
        idempotency_key=f"project.changed:2:checkpoint:{uuid4().hex[:8]}",
        payload={"pk": 2},
    )
    OutboxConsumerCheckpoint.objects.create(
        consumer=consumer,
        last_acked_event_id=first.id,
    )

    response = client.get(reverse("api-v1-outbox-events"), data={"consumer": consumer})

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["results"]] == [second.id]
    assert body["delivery"]["consumer"] == consumer
    assert body["delivery"]["checkpoint"] == first.id
    assert body["results"][0]["delivery_status"] == "pending"


def test_outbox_ack_endpoint_advances_checkpoint_and_is_idempotent():
    client = _auth_client()
    consumer = f"ml-{uuid4().hex[:8]}"
    event = OutboxEvent.objects.create(
        event_type="application.changed",
        aggregate_type="application",
        aggregate_id="42",
        idempotency_key=f"application.changed:42:ack:{uuid4().hex[:8]}",
        payload={"id": 42},
    )

    first_ack = client.post(
        reverse("api-v1-outbox-events-ack"),
        data={"consumer": consumer, "event_id": event.id},
    )
    second_ack = client.post(
        reverse("api-v1-outbox-events-ack"),
        data={"consumer": consumer, "event_id": event.id},
    )

    assert first_ack.status_code == 200
    assert first_ack.json()["ack_status"] == "advanced"
    assert second_ack.status_code == 200
    assert second_ack.json()["ack_status"] == "already_acked"
    assert second_ack.json()["last_acked_event_id"] == event.id


def test_outbox_ack_endpoint_requires_cpprp_or_staff_role():
    client = _auth_client(role=UserRole.STUDENT)
    event = OutboxEvent.objects.create(
        event_type="application.changed",
        aggregate_type="application",
        aggregate_id="42",
        idempotency_key=f"application.changed:42:ack-denied:{uuid4().hex[:8]}",
        payload={"id": 42},
    )

    response = client.post(
        reverse("api-v1-outbox-events-ack"),
        data={"consumer": f"ml-{uuid4().hex[:8]}", "event_id": event.id},
    )

    assert response.status_code == 403


def test_outbox_replay_mode_returns_acked_and_pending_events():
    client = _auth_client()
    consumer = f"graph-{uuid4().hex[:8]}"
    first = OutboxEvent.objects.create(
        event_type="user_profile.changed",
        aggregate_type="user_profile",
        aggregate_id="10",
        idempotency_key=f"user_profile.changed:10:replay:{uuid4().hex[:8]}",
        payload={"id": 10},
    )
    second = OutboxEvent.objects.create(
        event_type="user_profile.changed",
        aggregate_type="user_profile",
        aggregate_id="11",
        idempotency_key=f"user_profile.changed:11:replay:{uuid4().hex[:8]}",
        payload={"id": 11},
    )
    OutboxConsumerCheckpoint.objects.create(
        consumer=consumer,
        last_acked_event_id=first.id,
    )

    response = client.get(
        reverse("api-v1-outbox-events"),
        data={"consumer": consumer, "mode": "replay", "replay_from_id": first.id},
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert [item["id"] for item in results] == [first.id, second.id]
    assert [item["delivery_status"] for item in results] == ["acked", "pending"]


def test_outbox_checkpoint_endpoint_returns_resume_state():
    client = _auth_client()
    consumer = f"ml-{uuid4().hex[:8]}"
    checkpoint = OutboxConsumerCheckpoint.objects.create(
        consumer=consumer,
        last_acked_event_id=17,
        last_seen_event_id=19,
    )

    response = client.get(
        reverse("api-v1-outbox-consumer-checkpoint", kwargs={"consumer": checkpoint.consumer})
    )

    assert response.status_code == 200
    body = response.json()
    assert body["consumer"] == consumer
    assert body["last_acked_event_id"] == 17
    assert body["last_seen_event_id"] == 19
