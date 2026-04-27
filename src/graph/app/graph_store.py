from __future__ import annotations

import importlib
from typing import Any, Protocol, cast

from .models import GraphEvent

try:
    _neo4j_module = importlib.import_module("neo4j")
except ModuleNotFoundError:  # pragma: no cover - covered by startup checks
    _neo4j_module = None

GraphDatabase = _neo4j_module.GraphDatabase if _neo4j_module is not None else None


def _cypher(query: str) -> Any:
    if _neo4j_module is None:
        return query
    return _neo4j_module.Query(cast(Any, query))


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
            (
                "CREATE CONSTRAINT faculty_person_source_key_unique IF NOT EXISTS "
                "FOR (f:FacultyPerson) REQUIRE f.source_key IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT publication_source_publication_id_unique IF NOT EXISTS "
                "FOR (p:Publication) REQUIRE p.source_publication_id IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT course_course_key_unique IF NOT EXISTS "
                "FOR (c:Course) REQUIRE c.course_key IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT campus_campus_key_unique IF NOT EXISTS "
                "FOR (c:Campus) REQUIRE c.campus_key IS UNIQUE"
            ),
        ]

        with self._driver.session() as session:
            for statement in statements:
                session.run(_cypher(statement)).consume()

    def project_event(self, event: GraphEvent) -> None:
        aggregate_type = event.aggregate_type.strip().lower()
        if event.event_type == "project.deleted":
            self._delete_project(event)
            return
        if event.event_type == "application.deleted":
            self._delete_application(event)
            return
        if aggregate_type == "project":
            self._project_project(event)
            return
        if aggregate_type == "user_profile":
            self._project_profile(event)
            return
        if aggregate_type == "application":
            self._project_application(event)
            return
        if aggregate_type == "faculty_person":
            self._project_faculty_person(event)
            return
        if aggregate_type == "faculty_publication":
            self._project_faculty_publication(event)
            return
        if aggregate_type == "faculty_course":
            self._project_faculty_course(event)
            return
        if aggregate_type == "project_faculty_match":
            self._project_faculty_match(event)
            return

    def get_state_summary(self, *, consumer: str) -> dict[str, Any]:
        def _count(query: str) -> int:
            with self._driver.session() as session:
                record = session.run(_cypher(query)).single()
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
                "faculty_person": _count("MATCH (:FacultyPerson) RETURN count(*) AS count"),
                "publication": _count("MATCH (:Publication) RETURN count(*) AS count"),
                "course": _count("MATCH (:Course) RETURN count(*) AS count"),
            },
            "edges": _count("MATCH ()-[r]->() RETURN count(r) AS count"),
            "checkpoint_mirror": {
                "consumer": consumer,
                "last_acked_event_id": int(
                    checkpoint_record["last_acked_event_id"] if checkpoint_record else 0
                ),
                "updated_at": (str(checkpoint_record["updated_at"]) if checkpoint_record else None),
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

        query = _cypher("""
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
        """)

        with self._driver.session() as session:
            session.run(query, params).consume()

    def _project_faculty_person(self, event: GraphEvent) -> None:
        payload = event.payload
        source_key = _clean_string(payload.get("source_key") or event.aggregate_id)
        if source_key is None:
            return

        params = {
            "source_key": source_key,
            "source_person_id": _clean_string(payload.get("source_person_id")),
            "profile_url": _clean_string(payload.get("profile_url")),
            "full_name": _clean_string(payload.get("full_name")),
            "full_name_normalized": _clean_string(payload.get("full_name_normalized")),
            "primary_unit": _clean_string(payload.get("primary_unit")),
            "campus_id": _clean_string(payload.get("campus_id")),
            "campus_name": _clean_string(payload.get("campus_name")),
            "publications_total": int(payload.get("publications_total") or 0),
            "is_stale": bool(payload.get("is_stale") or False),
            "tags": self._normalize_tags(payload.get("interests") or []),
            "languages": payload.get("languages") or [],
            "source_hash": _clean_string(payload.get("source_hash")),
        }

        query = _cypher("""
        MERGE (f:FacultyPerson {source_key: $source_key})
        SET f.source_person_id = coalesce($source_person_id, f.source_person_id),
            f.profile_url = coalesce($profile_url, f.profile_url),
            f.full_name = coalesce($full_name, f.full_name),
            f.full_name_normalized = coalesce($full_name_normalized, f.full_name_normalized),
            f.primary_unit = coalesce($primary_unit, f.primary_unit),
            f.publications_total = $publications_total,
            f.languages = $languages,
            f.is_stale = $is_stale,
            f.source_hash = coalesce($source_hash, f.source_hash),
            f.updated_at = datetime()
        WITH f
        OPTIONAL MATCH (f)-[old_location:LOCATED_AT]->(:Campus)
        DELETE old_location
        WITH f
        FOREACH (_ IN CASE WHEN $campus_id IS NULL AND $campus_name IS NULL THEN [] ELSE [1] END |
            MERGE (c:Campus {campus_key: coalesce($campus_id, $campus_name)})
            SET c.campus_id = coalesce($campus_id, c.campus_id),
                c.name = coalesce($campus_name, c.name)
            MERGE (f)-[:LOCATED_AT]->(c)
        )
        WITH f, $tags AS tags
        OPTIONAL MATCH (f)-[old_interest:HAS_INTEREST]->(:Tag)
        DELETE old_interest
        WITH f, tags
        UNWIND tags AS tag
        MERGE (t:Tag {tag_name_normalized: tag.normalized})
        SET t.display_name = tag.display_name
        MERGE (f)-[:HAS_INTEREST]->(t)
        """)

        with self._driver.session() as session:
            session.run(query, params).consume()

    def _project_faculty_publication(self, event: GraphEvent) -> None:
        payload = event.payload
        source_publication_id = _clean_string(
            payload.get("source_publication_id") or event.aggregate_id
        )
        if source_publication_id is None:
            return

        authors = [
            author
            for author in (payload.get("authors") or [])
            if isinstance(author, dict) and author.get("person_source_key")
        ]
        params = {
            "source_publication_id": source_publication_id,
            "title": _clean_string(payload.get("title")),
            "type": _clean_string(payload.get("type")),
            "year": payload.get("year"),
            "language": _clean_string(payload.get("language")),
            "url": _clean_string(payload.get("url")),
            "source_hash": _clean_string(payload.get("source_hash")),
            "authors": authors,
        }

        query = _cypher("""
        MERGE (p:Publication {source_publication_id: $source_publication_id})
        SET p.title = coalesce($title, p.title),
            p.type = coalesce($type, p.type),
            p.year = $year,
            p.language = coalesce($language, p.language),
            p.url = coalesce($url, p.url),
            p.source_hash = coalesce($source_hash, p.source_hash),
            p.updated_at = datetime()
        WITH p
        OPTIONAL MATCH (:FacultyPerson)-[old_author:AUTHORED]->(p)
        DELETE old_author
        WITH p, $authors AS authors
        UNWIND authors AS author
        MERGE (f:FacultyPerson {source_key: author.person_source_key})
        MERGE (f)-[r:AUTHORED]->(p)
        SET r.position = author.position,
            r.display_name = author.display_name,
            r.href = author.href
        """)

        with self._driver.session() as session:
            session.run(query, params).consume()

    def _project_faculty_course(self, event: GraphEvent) -> None:
        payload = event.payload
        course_key = _clean_string(payload.get("course_key") or event.aggregate_id)
        person_source_key = _clean_string(payload.get("person_source_key"))
        if course_key is None or person_source_key is None:
            return

        params = {
            "course_key": course_key,
            "person_source_key": person_source_key,
            "title": _clean_string(payload.get("title")),
            "url": _clean_string(payload.get("url")),
            "academic_year": _clean_string(payload.get("academic_year")),
            "language": _clean_string(payload.get("language")),
            "level": _clean_string(payload.get("level")),
            "source_hash": _clean_string(payload.get("source_hash")),
        }
        query = _cypher("""
        MERGE (f:FacultyPerson {source_key: $person_source_key})
        MERGE (c:Course {course_key: $course_key})
        SET c.title = coalesce($title, c.title),
            c.url = coalesce($url, c.url),
            c.academic_year = coalesce($academic_year, c.academic_year),
            c.language = coalesce($language, c.language),
            c.level = coalesce($level, c.level),
            c.source_hash = coalesce($source_hash, c.source_hash),
            c.updated_at = datetime()
        MERGE (f)-[:TEACHES]->(c)
        """)
        with self._driver.session() as session:
            session.run(query, params).consume()

    def _project_faculty_match(self, event: GraphEvent) -> None:
        payload = event.payload
        project_id = _clean_string(payload.get("project_id") or event.aggregate_id)
        faculty_source_key = _clean_string(payload.get("faculty_source_key"))
        status = _clean_string(payload.get("status"))
        if project_id is None:
            return

        with self._driver.session() as session:
            session.run(
                _cypher("""
                MERGE (p:Project {project_id: $project_id})
                OPTIONAL MATCH (p)-[old_match:SUPERVISED_BY_FACULTY]->(:FacultyPerson)
                DELETE old_match
                """),
                {"project_id": project_id},
            ).consume()

            if status != "confirmed" or faculty_source_key is None:
                return

            session.run(
                _cypher("""
                MERGE (p:Project {project_id: $project_id})
                MERGE (f:FacultyPerson {source_key: $faculty_source_key})
                MERGE (p)-[r:SUPERVISED_BY_FACULTY]->(f)
                SET r.status = $status,
                    r.match_strategy = $match_strategy,
                    r.confidence = $confidence,
                    r.supervisor_name = $supervisor_name,
                    r.supervisor_email = $supervisor_email,
                    r.supervisor_department = $supervisor_department,
                    r.matched_at = $matched_at
                """),
                {
                    "project_id": project_id,
                    "faculty_source_key": faculty_source_key,
                    "status": status,
                    "match_strategy": _clean_string(payload.get("match_strategy")),
                    "confidence": float(payload.get("confidence") or 0),
                    "supervisor_name": _clean_string(payload.get("supervisor_name")),
                    "supervisor_email": _clean_string(payload.get("supervisor_email")),
                    "supervisor_department": _clean_string(payload.get("supervisor_department")),
                    "matched_at": _clean_string(payload.get("matched_at")),
                },
            ).consume()

    def _delete_project(self, event: GraphEvent) -> None:
        project_id = _clean_string(event.payload.get("pk") or event.aggregate_id)
        if project_id is None:
            return
        query = _cypher("""
        MATCH (p:Project {project_id: $project_id})
        DETACH DELETE p
        """)
        with self._driver.session() as session:
            session.run(query, {"project_id": project_id}).consume()

    def _delete_application(self, event: GraphEvent) -> None:
        application_id = _clean_string(event.payload.get("id") or event.aggregate_id)
        if application_id is None:
            return
        query = _cypher("""
        MATCH (a:Application {application_id: $application_id})
        DETACH DELETE a
        """)
        with self._driver.session() as session:
            session.run(query, {"application_id": application_id}).consume()

    def _project_profile(self, event: GraphEvent) -> None:
        payload = event.payload
        student_id = str(payload.get("id") or event.aggregate_id)

        params = {
            "student_id": student_id,
            "username": _clean_string(payload.get("username")),
            "email": _clean_string(payload.get("email")),
            "tags": self._normalize_tags(payload.get("interests") or []),
        }

        query = _cypher("""
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
        """)

        with self._driver.session() as session:
            session.run(query, params).consume()

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

        query = _cypher("""
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
        """)

        with self._driver.session() as session:
            session.run(query, params).consume()
