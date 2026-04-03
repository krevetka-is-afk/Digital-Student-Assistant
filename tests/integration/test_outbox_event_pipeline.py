from __future__ import annotations

import asyncio
import os
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from app.graph_store import Neo4jGraphStore
from app.models import GraphEvent
from app.projector import GraphProjector
from apps.outbox.models import OutboxEvent
from apps.outbox.services import (
    ack_event as ack_outbox_event,
)
from apps.outbox.services import (
    build_delivery_queryset,
    get_or_create_consumer_checkpoint,
    mark_polled,
)
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from neo4j import GraphDatabase

SAFE_NEO4J_HOSTS = {"localhost", "127.0.0.1", "neo4j"}


def _make_user(*, role: str | None = None, is_staff: bool = False):
    username = f"int-{uuid4().hex[:8]}"
    user = get_user_model().objects.create_user(
        username=username,
        password="placeholder",
        email=f"{username}@example.com",
        is_staff=is_staff,
    )
    if role is not None:
        UserProfile.objects.create(user=user, role=role)
    return user


def _exercise_business_change_flow(
    *,
    customer_client: Client,
    cpprp_client: Client,
    student_client: Client,
):
    suffix = uuid4().hex[:8]
    today = timezone.localdate()

    create_project_response = customer_client.post(
        reverse("api-v1-project-list"),
        data={
            "title": f"Integration stream project {suffix}",
            "description": "Outbox integration scenario.",
            "source_type": "initiative",
            "tech_tags": ["python", "graph"],
            "team_size": 1,
            "application_opened_at": (today - timedelta(days=1)).isoformat(),
            "application_deadline": (today + timedelta(days=14)).isoformat(),
        },
        content_type="application/json",
    )
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["pk"]

    submit_response = customer_client.post(
        reverse("api-v1-project-submit", kwargs={"pk": project_id}),
        content_type="application/json",
    )
    assert submit_response.status_code == 200

    moderate_response = cpprp_client.post(
        reverse("api-v1-project-moderate", kwargs={"pk": project_id}),
        data={"decision": "approve"},
        content_type="application/json",
    )
    assert moderate_response.status_code == 200

    profile_response = student_client.patch(
        reverse("user-profile-me"),
        data={"interests": ["python", "ml"]},
        content_type="application/json",
    )
    assert profile_response.status_code == 200

    apply_response = student_client.post(
        reverse("application-list"),
        data={
            "project": project_id,
            "motivation": "I have matching skills for this project.",
        },
        content_type="application/json",
    )
    assert apply_response.status_code == 201
    application_id = apply_response.json()["id"]

    review_response = customer_client.post(
        reverse("application-review", kwargs={"pk": application_id}),
        data={"decision": "accept"},
        content_type="application/json",
    )
    assert review_response.status_code == 200

    reindex_response = cpprp_client.post(
        reverse("api-v1-recs-reindex"),
        data={"reason": f"acceptance-{suffix}"},
        content_type="application/json",
    )
    assert reindex_response.status_code == 200


class DjangoOutboxClient:
    def __init__(self, *, consumer: str):
        self._consumer = consumer

    async def get_checkpoint(self) -> dict[str, Any]:
        checkpoint = get_or_create_consumer_checkpoint(self._consumer)
        return {
            "consumer": checkpoint.consumer,
            "status": checkpoint.status,
            "last_acked_event_id": checkpoint.last_acked_event_id,
            "last_seen_event_id": checkpoint.last_seen_event_id,
        }

    async def fetch_events(
        self,
        *,
        mode: str,
        batch_size: int,
        replay_from_id: int | None = None,
    ) -> list[GraphEvent]:
        checkpoint = get_or_create_consumer_checkpoint(self._consumer)
        queryset = (
            build_delivery_queryset(
                checkpoint=checkpoint,
                mode=mode,
                replay_from_id=replay_from_id,
            )
            .order_by("id")
            .all()[:batch_size]
        )
        events = [
            GraphEvent(
                id=item.id,
                event_type=item.event_type,
                aggregate_type=item.aggregate_type,
                aggregate_id=item.aggregate_id,
                source=item.source,
                idempotency_key=item.idempotency_key,
                payload=item.payload,
                created_at=item.created_at,
            )
            for item in queryset
        ]
        max_event_id = max((event.id for event in events if event.id is not None), default=None)
        mark_polled(checkpoint=checkpoint, max_event_id=max_event_id)
        return events

    async def ack_event(self, *, event_id: int) -> dict[str, Any]:
        checkpoint, ack_status = ack_outbox_event(consumer=self._consumer, event_id=event_id)
        return {
            "ack_status": ack_status,
            "consumer": checkpoint.consumer,
            "last_acked_event_id": checkpoint.last_acked_event_id,
        }


def _neo4j_config() -> tuple[str, str, str]:
    return (
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        os.getenv("NEO4J_USER", "neo4j"),
        os.getenv("NEO4J_PASSWORD", "test"),
    )


def _neo4j_is_available(*, uri: str, user: str, password: str) -> bool:
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1").consume()
        driver.close()
        return True
    except Exception:
        return False


def _reset_neo4j(*, uri: str, user: str, password: str) -> None:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
    driver.close()


def _is_neo4j_reset_allowed(uri: str) -> bool:
    parsed = urlparse(uri)
    host = (parsed.hostname or "").lower()
    return host in SAFE_NEO4J_HOSTS and os.getenv("ALLOW_NEO4J_RESET", "0") == "1"


@pytest.mark.integration
@pytest.mark.release_gate("RG-INTEGRATION-OUTBOX-DELIVERY")
def test_project_application_profile_changes_go_through_outbox_and_recs():
    customer = _make_user(role=UserRole.CUSTOMER)
    cpprp = _make_user(role=UserRole.CPPRP)
    student = _make_user(role=UserRole.STUDENT)

    customer_client = Client()
    customer_client.force_login(customer)

    cpprp_client = Client()
    cpprp_client.force_login(cpprp)

    student_client = Client()
    student_client.force_login(student)

    baseline_event_id = (
        OutboxEvent.objects.order_by("-id").values_list("id", flat=True).first() or 0
    )

    _exercise_business_change_flow(
        customer_client=customer_client,
        cpprp_client=cpprp_client,
        student_client=student_client,
    )

    new_event_types = set(
        OutboxEvent.objects.filter(id__gt=baseline_event_id).values_list("event_type", flat=True)
    )
    assert {
        "project.changed",
        "application.changed",
        "user_profile.changed",
        "recs.reindex_requested",
    }.issubset(new_event_types)

    consumer = f"graph-{uuid4().hex[:6]}"
    poll_response = cpprp_client.get(
        reverse("api-v1-outbox-events"),
        data={"consumer": consumer, "mode": "poll", "limit": 200},
    )
    assert poll_response.status_code == 200
    poll_payload = poll_response.json()
    assert poll_payload["delivery"]["consumer"] == consumer
    assert poll_payload["delivery"]["checkpoint"] == 0
    assert poll_payload["results"]

    scenario_results = [
        item for item in poll_payload["results"] if int(item["id"]) > int(baseline_event_id)
    ]
    assert scenario_results

    scenario_event_types = {item["event_type"] for item in scenario_results}
    assert {
        "project.changed",
        "application.changed",
        "user_profile.changed",
        "recs.reindex_requested",
    }.issubset(scenario_event_types)

    last_event_id = max(int(item["id"]) for item in scenario_results)
    ack_response = cpprp_client.post(
        reverse("api-v1-outbox-events-ack"),
        data={"consumer": consumer, "event_id": last_event_id},
        content_type="application/json",
    )
    assert ack_response.status_code == 200
    assert ack_response.json()["ack_status"] == "advanced"

    checkpoint_response = cpprp_client.get(
        reverse("api-v1-outbox-consumer-checkpoint", kwargs={"consumer": consumer})
    )
    assert checkpoint_response.status_code == 200
    assert int(checkpoint_response.json()["last_acked_event_id"]) == last_event_id


@pytest.mark.integration
@pytest.mark.release_gate("RG-INTEGRATION-OUTBOX-GRAPH-PROJECTION")
def test_graph_projector_consumes_django_outbox_stream():
    customer = _make_user(role=UserRole.CUSTOMER)
    cpprp = _make_user(role=UserRole.CPPRP)
    student = _make_user(role=UserRole.STUDENT)

    customer_client = Client()
    customer_client.force_login(customer)

    cpprp_client = Client()
    cpprp_client.force_login(cpprp)

    student_client = Client()
    student_client.force_login(student)

    baseline_event_id = (
        OutboxEvent.objects.order_by("-id").values_list("id", flat=True).first() or 0
    )

    _exercise_business_change_flow(
        customer_client=customer_client,
        cpprp_client=cpprp_client,
        student_client=student_client,
    )

    consumer = f"graph-{uuid4().hex[:8]}"
    if baseline_event_id:
        ack_outbox_event(consumer=consumer, event_id=int(baseline_event_id))

    uri, user, password = _neo4j_config()
    if not _neo4j_is_available(uri=uri, user=user, password=password):
        if os.getenv("ALLOW_LOCAL_GRAPH_SKIP", "0") == "1":
            pytest.skip("Neo4j unavailable locally; skip is explicitly allowed.")
        pytest.fail(
            "Neo4j is required for RG-INTEGRATION-OUTBOX-GRAPH-PROJECTION. "
            "Run with Neo4j or set ALLOW_LOCAL_GRAPH_SKIP=1 only for local development."
        )
    if not _is_neo4j_reset_allowed(uri):
        pytest.fail(
            "Refusing to wipe Neo4j for integration test. "
            "Set ALLOW_NEO4J_RESET=1 and use a local/container Neo4j host."
        )
    _reset_neo4j(uri=uri, user=user, password=password)

    graph_store = Neo4jGraphStore(uri=uri, user=user, password=password)
    graph_store.setup_schema()
    outbox_client = DjangoOutboxClient(consumer=consumer)
    projector = GraphProjector(
        graph_store=graph_store,
        outbox_client=outbox_client,
        consumer=consumer,
    )

    try:
        sync_result = asyncio.run(projector.sync_from_outbox(mode="poll", batch_size=500))
        assert sync_result["processed"] >= 4
        assert sync_result["last_event_id"] is not None
        assert sync_result["ack"] is not None
        assert sync_result["ack"]["ack_status"] == "advanced"

        summary = projector.state_summary()
        assert summary["nodes"]["project"] >= 1
        assert summary["nodes"]["student"] >= 1
        assert summary["nodes"]["application"] >= 1
        assert summary["nodes"]["tag"] >= 1
        assert summary["checkpoint_mirror"]["last_acked_event_id"] == sync_result["last_event_id"]
    finally:
        graph_store.close()
