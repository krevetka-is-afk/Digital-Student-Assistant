from uuid import uuid4

from apps.faculty.models import FacultyAuthorship, FacultyPerson, FacultyPublication
from apps.outbox.models import OutboxConsumerCheckpoint, OutboxEvent
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse
from rest_framework.test import APIClient


def _auth_client(role: str = UserRole.CPPRP) -> Client:
    user = get_user_model().objects.create_user(
        username=f"cpprp-outbox-{uuid4().hex[:8]}",
        password="placeholder",
    )
    UserProfile.objects.create(user=user, role=role)
    client = Client()
    client.force_login(user)
    return client


def _service_client(token: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
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
    OutboxConsumerCheckpoint.objects.create(consumer=consumer, last_acked_event_id=first.id)

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


def test_outbox_ack_endpoint_requires_cpprp_staff_or_service_token():
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
    OutboxConsumerCheckpoint.objects.create(consumer=consumer, last_acked_event_id=first.id)

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


@override_settings(OUTBOX_SERVICE_TOKENS={"ml": "ml-secret-token"})
def test_machine_token_can_poll_ack_and_read_checkpoint():
    client = _service_client("ml-secret-token")
    consumer = "ml"
    baseline = OutboxEvent.objects.order_by("-id").values_list("id", flat=True).first() or 0
    event = OutboxEvent.objects.create(
        event_type="project.changed",
        aggregate_type="project",
        aggregate_id="77",
        idempotency_key=f"project.changed:77:machine:{uuid4().hex[:8]}",
        payload={"pk": 77},
    )

    poll = client.get(
        reverse("api-v1-outbox-events"),
        data={"consumer": consumer, "since_id": baseline},
    )
    assert poll.status_code == 200
    assert [item["id"] for item in poll.json()["results"]] == [event.id]

    ack = client.post(
        reverse("api-v1-outbox-events-ack"),
        data={"consumer": consumer, "event_id": event.id},
    )
    assert ack.status_code == 200
    assert ack.json()["ack_status"] == "advanced"

    checkpoint = client.get(
        reverse("api-v1-outbox-consumer-checkpoint", kwargs={"consumer": consumer})
    )
    assert checkpoint.status_code == 200
    assert checkpoint.json()["last_acked_event_id"] == event.id


@override_settings(OUTBOX_SERVICE_TOKENS={"ml": "ml-secret-token"})
def test_invalid_machine_token_is_rejected_for_outbox_access():
    client = _service_client("wrong-token")

    response = client.get(reverse("api-v1-outbox-events"), data={"consumer": "ml"})

    assert response.status_code == 403


@override_settings(OUTBOX_SERVICE_TOKENS={"ml": "ml-secret-token"})
def test_snapshot_endpoint_returns_watermark_and_selected_resources():
    client = _service_client("ml-secret-token")
    OutboxEvent.objects.create(
        event_type="project.changed",
        aggregate_type="project",
        aggregate_id="99",
        idempotency_key=f"project.changed:99:snapshot:{uuid4().hex[:8]}",
        payload={"pk": 99},
    )

    response = client.get(
        reverse("api-v1-outbox-snapshot"),
        data={"resources": "projects,user_profiles"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["watermark"] >= 1
    assert body["resources"] == ["projects", "user_profiles"]
    assert "projects" in body
    assert "user_profiles" in body
    assert "applications" not in body


@override_settings(OUTBOX_SERVICE_TOKENS={"ml": "ml-secret-token"})
def test_snapshot_endpoint_includes_faculty_publication_authorships():
    client = _service_client("ml-secret-token")
    token = uuid4().hex[:8]
    person = FacultyPerson.objects.create(
        source_key=f"hse:{token}",
        source_person_id=token,
        source_profile_url=f"https://www.hse.ru/org/persons/{token}",
        full_name="Иванов Иван Иванович",
        full_name_normalized="иванов иван иванович",
        source_hash="person-hash",
    )
    publication = FacultyPublication.objects.create(
        source_publication_id=f"pub-{token}",
        title="Graph enrichment",
        source_hash="publication-hash",
    )
    FacultyAuthorship.objects.create(
        publication=publication,
        person=person,
        position=1,
        display_name=person.full_name,
    )

    response = client.get(
        reverse("api-v1-outbox-snapshot"),
        data={"resources": "faculty_publications"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resources"] == ["faculty_publications"]
    assert body["faculty_publications"][0]["source_publication_id"] == f"pub-{token}"
    assert body["faculty_publications"][0]["authors"] == [
        {
            "person_source_key": f"hse:{token}",
            "position": 1,
            "display_name": person.full_name,
            "href": "",
        }
    ]
