from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any, Protocol, cast

from .models import GraphEdge, GraphEvent, GraphNeighborsResponse, GraphNode, GraphSubgraphResponse

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

    def get_graph_meta(self, *, consumer: str) -> dict[str, Any]: ...

    def search_nodes(self, *, query: str, limit: int) -> list[GraphNode]: ...

    def get_neighbors(
        self,
        *,
        node_type: str,
        node_id: str,
        limit: int,
    ) -> GraphNeighborsResponse: ...

    def get_subgraph(
        self,
        *,
        node_type: str,
        node_id: str,
        depth: int,
    ) -> GraphSubgraphResponse: ...

    def set_checkpoint_mirror(self, *, consumer: str, last_acked_event_id: int) -> None: ...

    def close(self) -> None: ...


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


_NODE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "student": {
        "neo4j_label": "Student",
        "id_property": "student_id",
        "display_properties": ("username", "email", "student_id"),
        "search_properties": ("username", "email", "student_id"),
        "label": "Student",
    },
    "project": {
        "neo4j_label": "Project",
        "id_property": "project_id",
        "display_properties": ("title", "project_id"),
        "search_properties": ("title", "project_id", "status"),
        "label": "Project",
    },
    "supervisor": {
        "neo4j_label": "Supervisor",
        "id_property": "supervisor_key",
        "display_properties": ("name", "email", "supervisor_key"),
        "search_properties": ("name", "email", "supervisor_key"),
        "label": "Supervisor",
    },
    "tag": {
        "neo4j_label": "Tag",
        "id_property": "tag_name_normalized",
        "display_properties": ("display_name", "tag_name_normalized"),
        "search_properties": ("display_name", "tag_name_normalized"),
        "label": "Tag",
    },
    "application": {
        "neo4j_label": "Application",
        "id_property": "application_id",
        "display_properties": ("application_id", "status"),
        "search_properties": ("application_id", "status"),
        "label": "Application",
    },
}
_LABEL_TO_NODE_TYPE = {
    definition["neo4j_label"]: node_type for node_type, definition in _NODE_DEFINITIONS.items()
}
_EDGE_DEFINITIONS = (
    {
        "type": "SUPERVISED_BY",
        "source": "project",
        "target": "supervisor",
        "label": "Project supervised by supervisor",
    },
    {
        "type": "TAGGED_WITH",
        "source": "project",
        "target": "tag",
        "label": "Project tagged with technology",
    },
    {
        "type": "INTERESTED_IN",
        "source": "student",
        "target": "tag",
        "label": "Student interested in technology",
    },
    {
        "type": "SUBMITTED",
        "source": "student",
        "target": "application",
        "label": "Student submitted application",
    },
    {
        "type": "TARGETS",
        "source": "application",
        "target": "project",
        "label": "Application targets project",
    },
)


def _resolve_node_definition(node_type: str) -> dict[str, Any]:
    normalized = node_type.strip().lower()
    definition = _NODE_DEFINITIONS.get(normalized)
    if definition is None:
        raise ValueError(f"Unsupported graph node type '{node_type}'.")
    return definition


def _graph_node_key(node_type: str, node_id: str) -> str:
    return f"{node_type}:{node_id}"


def _clean_properties(properties: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dict(properties).items() if value is not None}


def _node_from_properties(*, node_type: str, properties: Mapping[str, Any]) -> GraphNode:
    definition = _resolve_node_definition(node_type)
    cleaned_properties = _clean_properties(properties)
    raw_node_id = _clean_string(cleaned_properties.get(definition["id_property"]))
    if raw_node_id is None:
        raise ValueError(f"Node '{node_type}' is missing identifier '{definition['id_property']}'.")

    label = next(
        (
            candidate
            for property_name in definition["display_properties"]
            if (candidate := _clean_string(cleaned_properties.get(property_name))) is not None
        ),
        raw_node_id,
    )
    cleaned_properties[definition["id_property"]] = raw_node_id
    return GraphNode(
        key=_graph_node_key(node_type, raw_node_id),
        type=node_type,
        id=raw_node_id,
        label=label,
        properties=cleaned_properties,
    )


def _edge_from_identifiers(
    *,
    relationship_type: str,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
) -> GraphEdge:
    return GraphEdge(
        type=relationship_type,
        source=_graph_node_key(source_type, source_id),
        target=_graph_node_key(target_type, target_id),
    )


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

    def get_graph_meta(self, *, consumer: str) -> dict[str, Any]:
        summary = self.get_state_summary(consumer=consumer)
        node_counts = summary["nodes"]
        return {
            "node_types": [
                {
                    "type": node_type,
                    "label": definition["label"],
                    "count": int(node_counts.get(node_type, 0)),
                }
                for node_type, definition in _NODE_DEFINITIONS.items()
            ],
            "edge_types": list(_EDGE_DEFINITIONS),
            "totals": {
                "nodes": int(sum(int(value) for value in node_counts.values())),
                "edges": int(summary["edges"]),
            },
            "checkpoint_mirror": summary["checkpoint_mirror"],
        }

    def search_nodes(self, *, query: str, limit: int) -> list[GraphNode]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        union_parts: list[str] = []
        for node_type, definition in _NODE_DEFINITIONS.items():
            contains_filters = " OR ".join(
                f"toLower(coalesce(toString(n.{property_name}), '')) CONTAINS $q"
                for property_name in definition["search_properties"]
            )
            exact_filters = " OR ".join(
                f"toLower(coalesce(toString(n.{property_name}), '')) = $q"
                for property_name in definition["search_properties"]
            )
            prefix_filters = " OR ".join(
                f"toLower(coalesce(toString(n.{property_name}), '')) STARTS WITH $q"
                for property_name in definition["search_properties"]
            )
            union_parts.append(
                f"""
                MATCH (n:{definition["neo4j_label"]})
                WHERE {contains_filters}
                RETURN '{node_type}' AS node_type,
                       properties(n) AS properties,
                       CASE
                           WHEN {exact_filters} THEN 0
                           WHEN {prefix_filters} THEN 1
                           ELSE 2
                       END AS rank
                """
            )

        query_text = _cypher(
            """
            CALL {
            """
            + "\nUNION ALL\n".join(union_parts)
            + """
            }
            RETURN node_type, properties, rank
            ORDER BY rank ASC, node_type ASC
            LIMIT $limit
            """
        )

        with self._driver.session() as session:
            records = list(session.run(query_text, {"q": normalized_query, "limit": limit}))

        items = [
            _node_from_properties(node_type=record["node_type"], properties=record["properties"])
            for record in records
        ]
        return sorted(items, key=lambda item: (item.label.lower(), item.type, item.id))[:limit]

    def get_neighbors(
        self,
        *,
        node_type: str,
        node_id: str,
        limit: int,
    ) -> GraphNeighborsResponse:
        center_node = self._fetch_node(node_type=node_type, node_id=node_id)
        definition = _resolve_node_definition(node_type)
        query = _cypher(
            f"""
            MATCH (n:{definition["neo4j_label"]} {{{definition["id_property"]}: $node_id}})
            OPTIONAL MATCH (n)-[r]-(m)
            RETURN type(r) AS relationship_type,
                   labels(startNode(r))[0] AS source_label,
                   properties(startNode(r)) AS source_properties,
                   labels(endNode(r))[0] AS target_label,
                   properties(endNode(r)) AS target_properties
            LIMIT $limit
            """
        )

        nodes_by_key: dict[str, GraphNode] = {center_node.key: center_node}
        edges: list[GraphEdge] = []
        with self._driver.session() as session:
            records = list(session.run(query, {"node_id": node_id, "limit": limit}))

        for record in records:
            relationship_type = record["relationship_type"]
            if relationship_type is None:
                continue
            source_type = _LABEL_TO_NODE_TYPE[record["source_label"]]
            target_type = _LABEL_TO_NODE_TYPE[record["target_label"]]
            source_node = _node_from_properties(
                node_type=source_type,
                properties=record["source_properties"],
            )
            target_node = _node_from_properties(
                node_type=target_type,
                properties=record["target_properties"],
            )
            nodes_by_key[source_node.key] = source_node
            nodes_by_key[target_node.key] = target_node
            edges.append(
                _edge_from_identifiers(
                    relationship_type=relationship_type,
                    source_type=source_type,
                    source_id=source_node.id,
                    target_type=target_type,
                    target_id=target_node.id,
                )
            )

        neighbors = sorted(
            (node for key, node in nodes_by_key.items() if key != center_node.key),
            key=lambda item: (item.type, item.label.lower(), item.id),
        )
        return GraphNeighborsResponse(node=center_node, neighbors=neighbors, edges=edges)

    def get_subgraph(
        self,
        *,
        node_type: str,
        node_id: str,
        depth: int,
    ) -> GraphSubgraphResponse:
        root_node = self._fetch_node(node_type=node_type, node_id=node_id)
        definition = _resolve_node_definition(node_type)
        query = _cypher(
            f"""
            MATCH (root:{definition["neo4j_label"]} {{{definition["id_property"]}: $node_id}})
            OPTIONAL MATCH path = (root)-[*1..{depth}]-(connected)
            UNWIND relationships(path) AS rel
            RETURN DISTINCT labels(startNode(rel))[0] AS source_label,
                            properties(startNode(rel)) AS source_properties,
                            type(rel) AS relationship_type,
                            labels(endNode(rel))[0] AS target_label,
                            properties(endNode(rel)) AS target_properties
            """
        )

        nodes_by_key: dict[str, GraphNode] = {root_node.key: root_node}
        edges_by_key: dict[tuple[str, str, str], GraphEdge] = {}
        with self._driver.session() as session:
            records = list(session.run(query, {"node_id": node_id}))

        for record in records:
            relationship_type = record["relationship_type"]
            if relationship_type is None:
                continue
            source_type = _LABEL_TO_NODE_TYPE[record["source_label"]]
            target_type = _LABEL_TO_NODE_TYPE[record["target_label"]]
            source_node = _node_from_properties(
                node_type=source_type,
                properties=record["source_properties"],
            )
            target_node = _node_from_properties(
                node_type=target_type,
                properties=record["target_properties"],
            )
            nodes_by_key[source_node.key] = source_node
            nodes_by_key[target_node.key] = target_node
            edge_key = (relationship_type, source_node.key, target_node.key)
            edges_by_key[edge_key] = _edge_from_identifiers(
                relationship_type=relationship_type,
                source_type=source_type,
                source_id=source_node.id,
                target_type=target_type,
                target_id=target_node.id,
            )

        nodes = sorted(
            nodes_by_key.values(),
            key=lambda item: (item.type, item.label.lower(), item.id),
        )
        edges = sorted(
            edges_by_key.values(),
            key=lambda item: (item.type, item.source, item.target),
        )
        return GraphSubgraphResponse(root=root_node, depth=depth, nodes=nodes, edges=edges)

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

    def _fetch_node(self, *, node_type: str, node_id: str) -> GraphNode:
        definition = _resolve_node_definition(node_type)
        query = _cypher(
            f"""
            MATCH (n:{definition["neo4j_label"]} {{{definition["id_property"]}: $node_id}})
            RETURN properties(n) AS properties
            """
        )
        with self._driver.session() as session:
            record = session.run(query, {"node_id": node_id}).single()
        if record is None:
            raise KeyError(f"Graph node '{node_type}:{node_id}' was not found.")
        return _node_from_properties(node_type=node_type, properties=record["properties"])

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
