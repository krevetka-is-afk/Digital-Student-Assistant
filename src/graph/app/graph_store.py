from __future__ import annotations

from typing import Any, Protocol

from .models import GraphEvent

try:
    from neo4j import GraphDatabase
except ModuleNotFoundError:  # pragma: no cover - covered by startup checks
    GraphDatabase = None


class GraphStore(Protocol):
    def setup_schema(self) -> None: ...

    def ping(self) -> None: ...

    def project_event(self, event: GraphEvent) -> None: ...

    def get_state_summary(self, *, consumer: str) -> dict[str, Any]: ...

    def set_checkpoint_mirror(self, *, consumer: str, last_acked_event_id: int) -> None: ...

    def close(self) -> None: ...


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


class Neo4jGraphStore:
    def __init__(self, *, uri: str, user: str, password: str):
        if GraphDatabase is None:
            raise RuntimeError("neo4j package is required for graph projector runtime.")
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    def ping(self) -> None:
        with self._driver.session() as session:
            session.run("RETURN 1").consume()

    def setup_schema(self) -> None:
        statements = [
            (
                "CREATE CONSTRAINT student_student_id_unique IF NOT EXISTS "
                "FOR (s:Student) REQUIRE s.student_id IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT project_project_id_unique IF NOT EXISTS "
                "FOR (p:Project) REQUIRE p.project_id IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT application_application_id_unique IF NOT EXISTS "
                "FOR (a:Application) REQUIRE a.application_id IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT supervisor_supervisor_key_unique IF NOT EXISTS "
                "FOR (s:Supervisor) REQUIRE s.supervisor_key IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT tag_name_unique IF NOT EXISTS "
                "FOR (t:Tag) REQUIRE t.tag_name_normalized IS UNIQUE"
            ),
        ]

        with self._driver.session() as session:
            for statement in statements:
                session.run(statement).consume()

    def project_event(self, event: GraphEvent) -> None:
        aggregate_type = event.aggregate_type.strip().lower()
        if aggregate_type == "project":
            self._project_project(event)
            return
        if aggregate_type == "user_profile":
            self._project_profile(event)
            return
        if aggregate_type == "application":
            self._project_application(event)
            return

    def get_state_summary(self, *, consumer: str) -> dict[str, Any]:
        def _count(query: str) -> int:
            with self._driver.session() as session:
                record = session.run(query).single()
            return int(record["count"] if record else 0)

        with self._driver.session() as session:
            checkpoint_record = session.run(
                """
                MATCH (c:ConsumerCheckpoint {consumer: $consumer})
                RETURN c.last_acked_event_id AS last_acked_event_id,
                       c.updated_at AS updated_at
                """,
                consumer=consumer,
            ).single()

        return {
            "nodes": {
                "student": _count("MATCH (:Student) RETURN count(*) AS count"),
                "project": _count("MATCH (:Project) RETURN count(*) AS count"),
                "supervisor": _count("MATCH (:Supervisor) RETURN count(*) AS count"),
                "tag": _count("MATCH (:Tag) RETURN count(*) AS count"),
                "application": _count("MATCH (:Application) RETURN count(*) AS count"),
            },
            "edges": _count("MATCH ()-[r]->() RETURN count(r) AS count"),
            "checkpoint_mirror": {
                "consumer": consumer,
                "last_acked_event_id": int(
                    checkpoint_record["last_acked_event_id"] if checkpoint_record else 0
                ),
                "updated_at": (
                    str(checkpoint_record["updated_at"]) if checkpoint_record else None
                ),
            },
        }

    def set_checkpoint_mirror(self, *, consumer: str, last_acked_event_id: int) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (c:ConsumerCheckpoint {consumer: $consumer})
                SET c.last_acked_event_id = $last_acked_event_id,
                    c.updated_at = datetime()
                """,
                consumer=consumer,
                last_acked_event_id=last_acked_event_id,
            ).consume()

    @staticmethod
    def _normalize_tags(raw_values: list[Any]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw_value in raw_values:
            display_name = _clean_string(raw_value)
            if display_name is None:
                continue
            normalized_value = display_name.lower()
            if normalized_value in seen:
                continue
            seen.add(normalized_value)
            normalized.append(
                {
                    "normalized": normalized_value,
                    "display_name": display_name,
                }
            )
        return normalized

    def _project_project(self, event: GraphEvent) -> None:
        payload = event.payload
        project_id = str(payload.get("pk") or payload.get("id") or event.aggregate_id)
        supervisor_email = _clean_string(payload.get("supervisor_email"))
        supervisor_name = _clean_string(payload.get("supervisor_name"))
        supervisor_key = (supervisor_email or supervisor_name or "").lower() or None

        params = {
            "project_id": project_id,
            "title": _clean_string(payload.get("title") or payload.get("vacancy_title")),
            "status": _clean_string(payload.get("status")),
            "updated_at": _clean_string(payload.get("updated_at")),
            "supervisor_key": supervisor_key,
            "supervisor_email": supervisor_email,
            "supervisor_name": supervisor_name,
            "tags": self._normalize_tags(payload.get("tech_tags") or []),
        }

        query = """
        MERGE (p:Project {project_id: $project_id})
        SET p.title = coalesce($title, p.title),
            p.status = coalesce($status, p.status),
            p.updated_at = coalesce($updated_at, p.updated_at)
        WITH p
        OPTIONAL MATCH (p)-[old_supervisor:SUPERVISED_BY]->(:Supervisor)
        DELETE old_supervisor
        WITH p
        FOREACH (_ IN CASE WHEN $supervisor_key IS NULL THEN [] ELSE [1] END |
            MERGE (s:Supervisor {supervisor_key: $supervisor_key})
            SET s.email = coalesce($supervisor_email, s.email),
                s.name = coalesce($supervisor_name, s.name)
            MERGE (p)-[:SUPERVISED_BY]->(s)
        )
        WITH p, $tags AS tags
        OPTIONAL MATCH (p)-[old_tag:TAGGED_WITH]->(:Tag)
        DELETE old_tag
        WITH p, tags
        UNWIND tags AS tag
        MERGE (t:Tag {tag_name_normalized: tag.normalized})
        SET t.display_name = tag.display_name
        MERGE (p)-[:TAGGED_WITH]->(t)
        """

        with self._driver.session() as session:
            session.run(query, **params).consume()

    def _project_profile(self, event: GraphEvent) -> None:
        payload = event.payload
        student_id = str(payload.get("id") or event.aggregate_id)

        params = {
            "student_id": student_id,
            "username": _clean_string(payload.get("username")),
            "email": _clean_string(payload.get("email")),
            "tags": self._normalize_tags(payload.get("interests") or []),
        }

        query = """
        MERGE (s:Student {student_id: $student_id})
        SET s.username = coalesce($username, s.username),
            s.email = coalesce($email, s.email)
        WITH s, $tags AS tags
        OPTIONAL MATCH (s)-[old_interest:INTERESTED_IN]->(:Tag)
        DELETE old_interest
        WITH s, tags
        UNWIND tags AS tag
        MERGE (t:Tag {tag_name_normalized: tag.normalized})
        SET t.display_name = tag.display_name
        MERGE (s)-[:INTERESTED_IN]->(t)
        """

        with self._driver.session() as session:
            session.run(query, **params).consume()

    def _project_application(self, event: GraphEvent) -> None:
        payload = event.payload
        application_id = str(payload.get("id") or event.aggregate_id)
        applicant_snapshot = payload.get("applicant_snapshot") or {}
        project_snapshot = payload.get("project_snapshot") or {}

        student_id = _clean_string(applicant_snapshot.get("id") or payload.get("applicant"))
        project_id = _clean_string(project_snapshot.get("pk") or payload.get("project"))

        params = {
            "application_id": application_id,
            "status": _clean_string(payload.get("status")),
            "updated_at": _clean_string(payload.get("updated_at")),
            "student_id": student_id,
            "student_username": _clean_string(applicant_snapshot.get("username")),
            "student_email": _clean_string(applicant_snapshot.get("email")),
            "project_id": project_id,
            "project_title": _clean_string(
                project_snapshot.get("title") or project_snapshot.get("vacancy_title")
            ),
        }

        query = """
        MERGE (a:Application {application_id: $application_id})
        SET a.status = coalesce($status, a.status),
            a.updated_at = coalesce($updated_at, a.updated_at)
        WITH a
        OPTIONAL MATCH (a)<-[old_submit:SUBMITTED]-(:Student)
        DELETE old_submit
        WITH a
        OPTIONAL MATCH (a)-[old_target:TARGETS]->(:Project)
        DELETE old_target
        WITH a
        FOREACH (_ IN CASE WHEN $student_id IS NULL THEN [] ELSE [1] END |
            MERGE (s:Student {student_id: $student_id})
            SET s.username = coalesce($student_username, s.username),
                s.email = coalesce($student_email, s.email)
            MERGE (s)-[:SUBMITTED]->(a)
        )
        FOREACH (_ IN CASE WHEN $project_id IS NULL THEN [] ELSE [1] END |
            MERGE (p:Project {project_id: $project_id})
            SET p.title = coalesce($project_title, p.title)
            MERGE (a)-[:TARGETS]->(p)
        )
        """

        with self._driver.session() as session:
            session.run(query, **params).consume()
