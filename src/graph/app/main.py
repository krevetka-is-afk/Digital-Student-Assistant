from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request

from .graph_store import GraphStore, Neo4jGraphStore
from .models import ProjectRequest, ReplayRequest, SyncRequest
from .outbox_client import HttpOutboxClient, OutboxClient
from .projector import GraphProjector
from .settings import GraphSettings, load_settings

logger = logging.getLogger(__name__)


def _serialize_graph_node(node: Any) -> dict[str, Any]:
    if hasattr(node, "type") and hasattr(node, "id") and hasattr(node, "label"):
        properties = dict(getattr(node, "properties", {}) or {})
        return {
            "node_type": str(getattr(node, "type")),
            "node_id": str(getattr(node, "id")),
            "label": str(getattr(node, "label")),
            "properties": properties,
        }
    return {
        "node_type": str(node["node_type"]),
        "node_id": str(node["node_id"]),
        "label": str(node["label"]),
        "properties": dict(node.get("properties", {})),
    }


def _serialize_graph_edge(edge: Any) -> dict[str, Any]:
    if hasattr(edge, "type") and hasattr(edge, "source") and hasattr(edge, "target"):
        source_type, source_id = str(getattr(edge, "source")).split(":", 1)
        target_type, target_id = str(getattr(edge, "target")).split(":", 1)
        return {
            "source_type": source_type,
            "source_id": source_id,
            "target_type": target_type,
            "target_id": target_id,
            "relationship_type": str(getattr(edge, "type")),
        }
    return {
        "source_type": str(edge["source_type"]),
        "source_id": str(edge["source_id"]),
        "target_type": str(edge["target_type"]),
        "target_id": str(edge["target_id"]),
        "relationship_type": str(edge["relationship_type"]),
    }



async def _poll_forever(app: FastAPI) -> None:
    stop_event: asyncio.Event = app.state.poller_stop_event
    settings: GraphSettings = app.state.settings
    projector: GraphProjector = app.state.projector

    while not stop_event.is_set():
        try:
            await projector.sync_from_outbox(mode="poll", batch_size=settings.default_batch_size)
        except Exception:
            logger.exception("Background poll cycle failed.")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.poll_interval_sec)
        except TimeoutError:
            continue


def _resolve_projector(request: Request) -> GraphProjector:
    projector = getattr(request.app.state, "projector", None)
    if projector is None:
        raise HTTPException(status_code=503, detail="Graph projector is not initialized.")
    return projector



def create_app(
    *,
    settings: GraphSettings | None = None,
    graph_store: GraphStore | None = None,
    outbox_client: OutboxClient | None = None,
) -> FastAPI:
    resolved_settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved_graph_store = graph_store or Neo4jGraphStore(
            uri=resolved_settings.neo4j_uri,
            user=resolved_settings.neo4j_user,
            password=resolved_settings.neo4j_password,
        )
        resolved_outbox_client = outbox_client or HttpOutboxClient(
            base_url=resolved_settings.outbox_base_url,
            consumer=resolved_settings.outbox_consumer,
            timeout_sec=resolved_settings.outbox_timeout_sec,
            auth_header=resolved_settings.outbox_auth_header,
        )

        resolved_graph_store.setup_schema()

        app.state.settings = resolved_settings
        app.state.graph_store = resolved_graph_store
        app.state.projector = GraphProjector(
            graph_store=resolved_graph_store,
            outbox_client=resolved_outbox_client,
            consumer=resolved_settings.outbox_consumer,
        )
        app.state.poller_stop_event = asyncio.Event()
        app.state.poller_task = None

        if resolved_settings.enable_background_poller:
            app.state.poller_task = asyncio.create_task(_poll_forever(app))

        try:
            yield
        finally:
            stop_event: asyncio.Event = app.state.poller_stop_event
            stop_event.set()
            poller_task: asyncio.Task[Any] | None = app.state.poller_task
            if poller_task is not None:
                await poller_task
            resolved_graph_store.close()

    app = FastAPI(title="Digital Student Assistant Graph Projector", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "graph"}

    @app.get("/ready")
    async def ready(request: Request) -> dict[str, Any]:
        projector = _resolve_projector(request)
        graph_store: GraphStore = request.app.state.graph_store

        neo4j_status = "ok"
        outbox_status = "ok"
        checkpoint: dict[str, Any] | None = None

        try:
            graph_store.ping()
        except Exception as exc:
            neo4j_status = f"error:{exc.__class__.__name__}"

        try:
            checkpoint = await projector.read_checkpoint()
        except Exception as exc:
            outbox_status = f"error:{exc.__class__.__name__}"

        status = "ok" if neo4j_status == "ok" and outbox_status == "ok" else "degraded"

        return {
            "status": status,
            "service": "graph",
            "neo4j": neo4j_status,
            "outbox": outbox_status,
            "consumer": request.app.state.settings.outbox_consumer,
            "checkpoint": checkpoint,
        }

    @app.get("/state")
    async def state(request: Request) -> dict[str, Any]:
        projector = _resolve_projector(request)
        summary = projector.state_summary()

        checkpoint: dict[str, Any] | None = None
        try:
            checkpoint = await projector.read_checkpoint()
        except Exception:
            checkpoint = None

        return {
            **summary,
            "checkpoint": checkpoint,
        }

    @app.get("/graph/meta")
    async def meta(request: Request) -> dict[str, Any]:
        projector = _resolve_projector(request)
        return projector.meta()

    @app.get("/graph/search")
    async def search(
        request: Request,
        q: str = Query(..., min_length=1, description="Case-insensitive graph node search."),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> dict[str, Any]:
        projector = _resolve_projector(request)
        items = projector.search(query=q, limit=limit)
        return {
            "query": q,
            "limit": limit,
            "items": [_serialize_graph_node(item) for item in items],
        }

    @app.get("/graph/nodes/{node_type}/{node_id}/neighbors")
    async def neighbors(
        node_type: str,
        node_id: str,
        request: Request,
        limit: int = Query(default=25, ge=1, le=100),
    ) -> dict[str, Any]:
        projector = _resolve_projector(request)
        try:
            payload = projector.neighbors(node_type=node_type, node_id=node_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        focus_payload = getattr(payload, "node", None)
        neighbors_items = getattr(payload, "neighbors", None)
        edges_items = getattr(payload, "edges", None)
        if focus_payload is not None and neighbors_items is not None and edges_items is not None:
            focus = _serialize_graph_node(focus_payload)
            nodes = [focus, *[_serialize_graph_node(item) for item in neighbors_items]]
        else:
            payload_map = (
                payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
            )
            focus = {
                "node_type": str(payload_map["focus"]["node_type"]),
                "node_id": str(payload_map["focus"]["node_id"]),
            }
            nodes = [_serialize_graph_node(item) for item in payload_map["nodes"]]
            edges_items = payload_map["edges"]
        return {
            "focus": {"node_type": focus["node_type"], "node_id": focus["node_id"]},
            "depth": 1,
            "nodes": nodes,
            "edges": [_serialize_graph_edge(item) for item in edges_items],
        }

    @app.get("/graph/subgraph")
    async def subgraph(
        request: Request,
        node_type: str = Query(...),
        node_id: str = Query(...),
        depth: int = Query(default=2, ge=1, le=3),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        del limit
        projector = _resolve_projector(request)
        try:
            payload = projector.subgraph(node_type=node_type, node_id=node_id, depth=depth)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        root_payload = getattr(payload, "root", None)
        nodes_items = getattr(payload, "nodes", None)
        edges_items = getattr(payload, "edges", None)
        if root_payload is not None and nodes_items is not None and edges_items is not None:
            root = _serialize_graph_node(root_payload)
            depth_value = int(getattr(payload, "depth"))
            nodes = [_serialize_graph_node(item) for item in nodes_items]
        else:
            payload_map = (
                payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
            )
            root = {
                "node_type": str(payload_map["focus"]["node_type"]),
                "node_id": str(payload_map["focus"]["node_id"]),
            }
            depth_value = int(payload_map["depth"])
            nodes = [_serialize_graph_node(item) for item in payload_map["nodes"]]
            edges_items = payload_map["edges"]
        return {
            "focus": {"node_type": root["node_type"], "node_id": root["node_id"]},
            "depth": depth_value,
            "nodes": nodes,
            "edges": [_serialize_graph_edge(item) for item in edges_items],
        }

    @app.get("/meta")
    async def meta_legacy(request: Request) -> dict[str, Any]:
        return await meta(request)

    @app.get("/search")
    async def search_legacy(
        request: Request,
        q: str = Query(..., min_length=1, description="Case-insensitive graph node search."),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> dict[str, Any]:
        return await search(request=request, q=q, limit=limit)

    @app.get("/neighbors/{node_type}/{node_id}")
    async def neighbors_legacy(
        node_type: str,
        node_id: str,
        request: Request,
        limit: int = Query(default=25, ge=1, le=100),
    ) -> dict[str, Any]:
        return await neighbors(node_type=node_type, node_id=node_id, request=request, limit=limit)

    @app.get("/subgraph/{node_type}/{node_id}")
    async def subgraph_legacy(
        node_type: str,
        node_id: str,
        request: Request,
        depth: int = Query(default=2, ge=1, le=3),
    ) -> dict[str, Any]:
        return await subgraph(request=request, node_type=node_type, node_id=node_id, depth=depth)

    @app.post("/project")
    async def project_events(payload: ProjectRequest, request: Request) -> dict[str, Any]:
        projector = _resolve_projector(request)
        projection = projector.project_events(payload.events)
        return {
            "status": "accepted",
            "processed": projection["processed"],
            "last_event_id": projection["last_event_id"],
            "source": "direct",
        }

    @app.post("/sync")
    async def sync(payload: SyncRequest, request: Request) -> dict[str, Any]:
        projector = _resolve_projector(request)
        batch_size = payload.batch_size or request.app.state.settings.default_batch_size
        result = await projector.sync_from_outbox(mode="poll", batch_size=batch_size)
        return {
            "status": "accepted",
            **result,
        }

    @app.post("/replay")
    async def replay(payload: ReplayRequest, request: Request) -> dict[str, Any]:
        projector = _resolve_projector(request)
        batch_size = payload.batch_size or request.app.state.settings.default_batch_size

        if payload.events:
            projection = projector.project_events(payload.events)
            return {
                "status": "accepted",
                "replayed": projection["processed"],
                "last_event_id": projection["last_event_id"],
                "source": "direct",
            }

        if payload.replay_from_id is None:
            raise HTTPException(
                status_code=422,
                detail="replay_from_id is required when events are not provided.",
            )

        result = await projector.sync_from_outbox(
            mode="replay",
            batch_size=batch_size,
            replay_from_id=payload.replay_from_id,
        )
        return {
            "status": "accepted",
            "replayed": result["processed"],
            "last_event_id": result["last_event_id"],
            "ack": result["ack"],
            "source": "outbox",
        }

    return app


app = create_app()
