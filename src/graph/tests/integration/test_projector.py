from __future__ import annotations

from typing import Any, TypedDict, cast

from starlette.testclient import TestClient

from src.graph.app.models import GraphEvent


class FakeGraphStore:
    def __init__(self):
        self.students: set[str] = set()
        self.projects: set[str] = set()
        self.supervisors: set[str] = set()
        self.tags: set[str] = set()
        self.applications: set[str] = set()
        self.faculty_persons: set[str] = set()
        self.publications: set[str] = set()
        self.courses: set[str] = set()

        self.project_supervisor_edges: set[tuple[str, str]] = set()
        self.project_faculty_edges: set[tuple[str, str]] = set()
        self.project_tag_edges: set[tuple[str, str]] = set()
        self.student_interest_edges: set[tuple[str, str]] = set()
        self.student_application_edges: set[tuple[str, str]] = set()
        self.application_project_edges: set[tuple[str, str]] = set()
        self.faculty_interest_edges: set[tuple[str, str]] = set()
        self.faculty_publication_edges: set[tuple[str, str]] = set()
        self.faculty_course_edges: set[tuple[str, str]] = set()
        self.faculty_location_edges: set[tuple[str, str]] = set()

        self._project_supervisor_map: dict[str, str | None] = {}
        self._project_tags_map: dict[str, set[str]] = {}
        self._student_tags_map: dict[str, set[str]] = {}
        self._application_submitter_map: dict[str, str | None] = {}
        self._application_target_map: dict[str, str | None] = {}

        self._checkpoint_by_consumer: dict[str, int] = {}

    def setup_schema(self) -> None:
        return

    def ping(self) -> None:
        return

    def close(self) -> None:
        return

    def set_checkpoint_mirror(self, *, consumer: str, last_acked_event_id: int) -> None:
        self._checkpoint_by_consumer[consumer] = last_acked_event_id

    def get_state_summary(self, *, consumer: str) -> dict[str, Any]:
        return {
            "nodes": {
                "student": len(self.students),
                "project": len(self.projects),
                "supervisor": len(self.supervisors),
                "tag": len(self.tags),
                "application": len(self.applications),
                "faculty_person": len(self.faculty_persons),
                "publication": len(self.publications),
                "course": len(self.courses),
            },
            "edges": (
                len(self.project_supervisor_edges)
                + len(self.project_faculty_edges)
                + len(self.project_tag_edges)
                + len(self.student_interest_edges)
                + len(self.student_application_edges)
                + len(self.application_project_edges)
                + len(self.faculty_interest_edges)
                + len(self.faculty_publication_edges)
                + len(self.faculty_course_edges)
                + len(self.faculty_location_edges)
            ),
            "checkpoint_mirror": {
                "consumer": consumer,
                "last_acked_event_id": self._checkpoint_by_consumer.get(consumer, 0),
                "updated_at": None,
            },
        }

    def project_event(self, event: GraphEvent) -> None:
        aggregate_type = event.aggregate_type.lower().strip()
        payload = event.payload

        if event.event_type == "project.deleted":
            project_id = str(payload.get("pk") or event.aggregate_id)
            self.projects.discard(project_id)
            self.project_supervisor_edges = {
                edge for edge in self.project_supervisor_edges if edge[0] != project_id
            }
            self.project_tag_edges = {
                edge for edge in self.project_tag_edges if edge[0] != project_id
            }
            self.application_project_edges = {
                edge for edge in self.application_project_edges if edge[1] != project_id
            }
            self.project_faculty_edges = {
                edge for edge in self.project_faculty_edges if edge[0] != project_id
            }
            self._project_supervisor_map.pop(project_id, None)
            self._project_tags_map.pop(project_id, None)
            return

        if event.event_type == "application.deleted":
            application_id = str(payload.get("id") or event.aggregate_id)
            self.applications.discard(application_id)
            self.student_application_edges = {
                edge for edge in self.student_application_edges if edge[1] != application_id
            }
            self.application_project_edges = {
                edge for edge in self.application_project_edges if edge[0] != application_id
            }
            self._application_submitter_map.pop(application_id, None)
            self._application_target_map.pop(application_id, None)
            return

        if aggregate_type == "project":
            project_id = str(payload.get("pk") or payload.get("id") or event.aggregate_id)
            self.projects.add(project_id)

            supervisor = (
                payload.get("supervisor_email") or payload.get("supervisor_name") or ""
            ).strip()
            supervisor_key = supervisor.lower() if supervisor else None
            previous_supervisor = self._project_supervisor_map.get(project_id)
            if previous_supervisor is not None:
                self.project_supervisor_edges.discard((project_id, previous_supervisor))
            self._project_supervisor_map[project_id] = supervisor_key
            if supervisor_key is not None:
                self.supervisors.add(supervisor_key)
                self.project_supervisor_edges.add((project_id, supervisor_key))

            new_tags = {
                str(tag).strip().lower() for tag in payload.get("tech_tags", []) if str(tag).strip()
            }
            for old_tag in self._project_tags_map.get(project_id, set()):
                self.project_tag_edges.discard((project_id, old_tag))
            self._project_tags_map[project_id] = new_tags
            for tag in new_tags:
                self.tags.add(tag)
                self.project_tag_edges.add((project_id, tag))
            return

        if aggregate_type == "user_profile":
            student_id = str(payload.get("id") or event.aggregate_id)
            self.students.add(student_id)

            new_tags = {
                str(tag).strip().lower() for tag in payload.get("interests", []) if str(tag).strip()
            }
            for old_tag in self._student_tags_map.get(student_id, set()):
                self.student_interest_edges.discard((student_id, old_tag))
            self._student_tags_map[student_id] = new_tags
            for tag in new_tags:
                self.tags.add(tag)
                self.student_interest_edges.add((student_id, tag))
            return

        if aggregate_type == "application":
            application_id = str(payload.get("id") or event.aggregate_id)
            self.applications.add(application_id)

            previous_submitter = self._application_submitter_map.get(application_id)
            if previous_submitter is not None:
                self.student_application_edges.discard((previous_submitter, application_id))

            applicant_snapshot = payload.get("applicant_snapshot") or {}
            student_id = applicant_snapshot.get("id") or payload.get("applicant")
            if student_id is not None:
                normalized_student_id = str(student_id)
                self.students.add(normalized_student_id)
                self._application_submitter_map[application_id] = normalized_student_id
                self.student_application_edges.add((normalized_student_id, application_id))
            else:
                self._application_submitter_map[application_id] = None

            previous_target = self._application_target_map.get(application_id)
            if previous_target is not None:
                self.application_project_edges.discard((application_id, previous_target))

            project_snapshot = payload.get("project_snapshot") or {}
            project_id = project_snapshot.get("pk") or payload.get("project")
            if project_id is not None:
                normalized_project_id = str(project_id)
                self.projects.add(normalized_project_id)
                self._application_target_map[application_id] = normalized_project_id
                self.application_project_edges.add((application_id, normalized_project_id))
            else:
                self._application_target_map[application_id] = None
            return

        if aggregate_type == "faculty_person":
            source_key = str(payload.get("source_key") or event.aggregate_id)
            self.faculty_persons.add(source_key)
            for old_edge in {edge for edge in self.faculty_interest_edges if edge[0] == source_key}:
                self.faculty_interest_edges.discard(old_edge)
            for old_edge in {edge for edge in self.faculty_location_edges if edge[0] == source_key}:
                self.faculty_location_edges.discard(old_edge)
            campus = payload.get("campus_id") or payload.get("campus_name")
            if campus:
                self.faculty_location_edges.add((source_key, str(campus)))
            for interest in payload.get("interests", []):
                tag = str(interest).strip().lower()
                if not tag:
                    continue
                self.tags.add(tag)
                self.faculty_interest_edges.add((source_key, tag))
            return

        if aggregate_type == "faculty_publication":
            publication_id = str(payload.get("source_publication_id") or event.aggregate_id)
            self.publications.add(publication_id)
            self.faculty_publication_edges = {
                edge for edge in self.faculty_publication_edges if edge[1] != publication_id
            }
            for author in payload.get("authors", []):
                source_key = author.get("person_source_key")
                if source_key:
                    self.faculty_persons.add(str(source_key))
                    self.faculty_publication_edges.add((str(source_key), publication_id))
            return

        if aggregate_type == "faculty_course":
            course_key = str(payload.get("course_key") or event.aggregate_id)
            source_key = payload.get("person_source_key")
            self.courses.add(course_key)
            if source_key:
                self.faculty_persons.add(str(source_key))
                self.faculty_course_edges.add((str(source_key), course_key))
            return

        if aggregate_type == "project_faculty_match":
            project_id = str(payload.get("project_id") or event.aggregate_id)
            self.project_faculty_edges = {
                edge for edge in self.project_faculty_edges if edge[0] != project_id
            }
            source_key = payload.get("faculty_source_key")
            if payload.get("status") == "confirmed" and source_key:
                self.projects.add(project_id)
                self.faculty_persons.add(str(source_key))
                self.project_faculty_edges.add((project_id, str(source_key)))


class _CheckpointState(TypedDict):
    consumer: str
    status: str
    last_acked_event_id: int
    last_seen_event_id: int
    metadata: dict[str, Any]


class FakeOutboxClient:
    def __init__(self, *, events: list[GraphEvent], initial_checkpoint: int = 0):
        self._events = sorted(events, key=lambda event: event.id or 0)
        self._checkpoint: _CheckpointState = {
            "consumer": "graph",
            "status": "active",
            "last_acked_event_id": initial_checkpoint,
            "last_seen_event_id": initial_checkpoint,
            "metadata": {},
        }
        self.calls: list[dict[str, Any]] = []

    async def get_checkpoint(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._checkpoint.copy())

    async def fetch_events(
        self,
        *,
        mode: str,
        batch_size: int,
        replay_from_id: int | None = None,
    ) -> list[GraphEvent]:
        self.calls.append(
            {
                "mode": mode,
                "batch_size": batch_size,
                "replay_from_id": replay_from_id,
            }
        )

        if mode == "replay":
            lower_bound = max((replay_from_id or 1) - 1, 0)
        else:
            lower_bound = self._checkpoint["last_acked_event_id"]

        return [event for event in self._events if (event.id or 0) > lower_bound][:batch_size]

    async def ack_event(self, *, event_id: int) -> dict[str, Any]:
        if event_id <= self._checkpoint["last_acked_event_id"]:
            status = "already_acked"
        else:
            status = "advanced"
            self._checkpoint["last_acked_event_id"] = event_id
        self._checkpoint["last_seen_event_id"] = max(
            self._checkpoint["last_seen_event_id"], event_id
        )

        return {
            "ack_status": status,
            **self._checkpoint,
        }


def _make_client(app_factory, *, events: list[GraphEvent], initial_checkpoint: int = 0):
    graph_store = FakeGraphStore()
    outbox_client = FakeOutboxClient(events=events, initial_checkpoint=initial_checkpoint)
    app = app_factory(graph_store=graph_store, outbox_client=outbox_client)
    return TestClient(app), graph_store, outbox_client


def test_health_ok(app_factory):
    client, _, _ = _make_client(app_factory, events=[])
    with client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "graph"}


def test_projector_supports_canonical_nodes_and_relationships(app_factory):
    events = [
        GraphEvent(
            id=1,
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id="1",
            payload={
                "pk": 1,
                "supervisor_email": "mentor@example.com",
                "tech_tags": ["python", "ml"],
            },
        ),
        GraphEvent(
            id=2,
            event_type="user_profile.changed",
            aggregate_type="user_profile",
            aggregate_id="7",
            payload={"id": 7, "interests": ["ml", "data"]},
        ),
        GraphEvent(
            id=3,
            event_type="application.changed",
            aggregate_type="application",
            aggregate_id="50",
            payload={
                "id": 50,
                "applicant_snapshot": {"id": 7},
                "project_snapshot": {"pk": 1},
            },
        ),
    ]

    client, _, _ = _make_client(app_factory, events=[])
    with client:
        response = client.post(
            "/project",
            json={"events": [event.model_dump(mode="json") for event in events]},
        )
        state = client.get("/state")

    assert response.status_code == 200
    assert response.json()["processed"] == 3

    assert state.status_code == 200
    payload = state.json()
    assert payload["nodes"]["student"] == 1
    assert payload["nodes"]["project"] == 1
    assert payload["nodes"]["supervisor"] == 1
    assert payload["nodes"]["tag"] == 3
    assert payload["nodes"]["application"] == 1
    assert payload["edges"] == 7
    assert payload["checkpoint_mirror"]["last_acked_event_id"] == 0


def test_projector_supports_faculty_enrichment_events(app_factory):
    events = [
        GraphEvent(
            id=1,
            event_type="faculty.person.changed",
            aggregate_type="faculty_person",
            aggregate_id="hse:25477",
            payload={
                "source_key": "hse:25477",
                "full_name": "Абанкина Ирина Всеволодовна",
                "interests": ["education", "analytics"],
            },
        ),
        GraphEvent(
            id=2,
            event_type="faculty.publication.changed",
            aggregate_type="faculty_publication",
            aggregate_id="pub-1",
            payload={
                "source_publication_id": "pub-1",
                "title": "Student projects",
                "authors": [{"person_source_key": "hse:25477", "position": 0}],
            },
        ),
        GraphEvent(
            id=3,
            event_type="faculty.course.changed",
            aggregate_type="faculty_course",
            aggregate_id="course-1",
            payload={
                "course_key": "course-1",
                "person_source_key": "hse:25477",
                "title": "Project seminar",
            },
        ),
        GraphEvent(
            id=4,
            event_type="project_faculty_match.changed",
            aggregate_type="project_faculty_match",
            aggregate_id="101",
            payload={
                "project_id": "101",
                "faculty_source_key": "hse:25477",
                "status": "confirmed",
                "match_strategy": "name_department",
                "confidence": 0.85,
            },
        ),
    ]

    client, graph_store, _ = _make_client(app_factory, events=[])
    with client:
        response = client.post(
            "/project",
            json={"events": [event.model_dump(mode="json") for event in events]},
        )
        state = client.get("/state")

    assert response.status_code == 200
    assert graph_store.project_faculty_edges == {("101", "hse:25477")}
    assert graph_store.faculty_publication_edges == {("hse:25477", "pub-1")}
    assert graph_store.faculty_course_edges == {("hse:25477", "course-1")}

    payload = state.json()
    assert payload["nodes"]["faculty_person"] == 1
    assert payload["nodes"]["publication"] == 1
    assert payload["nodes"]["course"] == 1


def test_projector_replaces_faculty_location_edges(app_factory):
    events = [
        GraphEvent(
            id=1,
            event_type="faculty.person.changed",
            aggregate_type="faculty_person",
            aggregate_id="hse:25477",
            payload={"source_key": "hse:25477", "campus_id": "msk"},
        ),
        GraphEvent(
            id=2,
            event_type="faculty.person.changed",
            aggregate_type="faculty_person",
            aggregate_id="hse:25477",
            payload={"source_key": "hse:25477", "campus_id": "spb"},
        ),
    ]

    client, graph_store, _ = _make_client(app_factory, events=[])
    with client:
        response = client.post(
            "/project",
            json={"events": [event.model_dump(mode="json") for event in events]},
        )

    assert response.status_code == 200
    assert graph_store.faculty_location_edges == {("hse:25477", "spb")}


def test_sync_uses_outbox_poll_and_updates_checkpoint(app_factory):
    events = [
        GraphEvent(
            id=11,
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id="11",
            payload={"pk": 11, "tech_tags": ["python"]},
        ),
        GraphEvent(
            id=12,
            event_type="user_profile.changed",
            aggregate_type="user_profile",
            aggregate_id="5",
            payload={"id": 5, "interests": ["python"]},
        ),
    ]

    client, _, outbox_client = _make_client(app_factory, events=events)
    with client:
        response = client.post("/sync", json={"batch_size": 10})
        state = client.get("/state")

    assert response.status_code == 200
    body = response.json()
    assert body["processed"] == 2
    assert body["last_event_id"] == 12
    assert body["ack"]["ack_status"] == "advanced"

    assert outbox_client.calls[-1]["mode"] == "poll"

    assert state.status_code == 200
    payload = state.json()
    assert payload["checkpoint"]["last_acked_event_id"] == 12
    assert payload["checkpoint_mirror"]["last_acked_event_id"] == 12


def test_replay_mode_reprocesses_from_offset_and_acks(app_factory):
    events = [
        GraphEvent(
            id=1,
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id="1",
            payload={"pk": 1, "tech_tags": ["python"]},
        ),
        GraphEvent(
            id=2,
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id="2",
            payload={"pk": 2, "tech_tags": ["ml"]},
        ),
        GraphEvent(
            id=3,
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id="3",
            payload={"pk": 3, "tech_tags": ["nlp"]},
        ),
    ]

    client, _, outbox_client = _make_client(app_factory, events=events)
    with client:
        response = client.post("/replay", json={"replay_from_id": 2, "batch_size": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["replayed"] == 2
    assert body["last_event_id"] == 3
    assert body["source"] == "outbox"
    assert body["ack"]["ack_status"] == "advanced"

    assert outbox_client.calls[-1]["mode"] == "replay"
    assert outbox_client.calls[-1]["replay_from_id"] == 2


def test_checkpoint_recovery_starts_from_existing_acked_offset(app_factory):
    events = [
        GraphEvent(
            id=7,
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id="7",
            payload={"pk": 7, "tech_tags": ["legacy"]},
        ),
        GraphEvent(
            id=8,
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id="8",
            payload={"pk": 8, "tech_tags": ["new"]},
        ),
    ]

    client, _, _ = _make_client(app_factory, events=events, initial_checkpoint=7)
    with client:
        ready = client.get("/ready")
        sync = client.post("/sync", json={"batch_size": 10})

    assert ready.status_code == 200
    ready_payload = ready.json()
    assert ready_payload["checkpoint"]["last_acked_event_id"] == 7

    assert sync.status_code == 200
    sync_payload = sync.json()
    assert sync_payload["processed"] == 1
    assert sync_payload["last_event_id"] == 8


def test_replay_requires_offset_when_direct_events_are_not_given(app_factory):
    client, _, _ = _make_client(app_factory, events=[])
    with client:
        response = client.post("/replay", json={})

    assert response.status_code == 422
    assert "replay_from_id is required" in response.json()["detail"]


def test_delete_events_remove_project_and_application_nodes(app_factory):
    events = [
        GraphEvent(
            id=1,
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id="1",
            payload={"pk": 1, "tech_tags": ["python"]},
        ),
        GraphEvent(
            id=2,
            event_type="application.changed",
            aggregate_type="application",
            aggregate_id="50",
            payload={"id": 50, "applicant_snapshot": {"id": 7}, "project_snapshot": {"pk": 1}},
        ),
        GraphEvent(
            id=3,
            event_type="application.deleted",
            aggregate_type="application",
            aggregate_id="50",
            payload={"id": 50, "tombstone": True},
        ),
        GraphEvent(
            id=4,
            event_type="project.deleted",
            aggregate_type="project",
            aggregate_id="1",
            payload={"pk": 1, "tombstone": True},
        ),
    ]

    client, _, _ = _make_client(app_factory, events=[])
    with client:
        response = client.post(
            "/project",
            json={"events": [event.model_dump(mode="json") for event in events]},
        )
        state = client.get("/state")

    assert response.status_code == 200
    payload = state.json()
    assert payload["nodes"]["project"] == 0
    assert payload["nodes"]["application"] == 0
