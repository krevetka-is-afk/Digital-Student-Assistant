from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from .graph_store import GraphStore, Neo4jGraphStore
from .models import ProjectRequest, ReplayRequest, SyncRequest
from .outbox_client import HttpOutboxClient, OutboxClient
from .projector import GraphProjector
from .settings import GraphSettings, load_settings

logger = logging.getLogger(__name__)


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
