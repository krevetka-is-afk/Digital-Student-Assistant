from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from .index_store import RecommendationIndexStore
from .models import (
    OutboxEvent,
    ProjectPayload,
    ProjectRequest,
    RankedResponse,
    RecommendationRequest,
    ReindexRequest,
    ReindexResponse,
    ReplayRequest,
    SearchRequest,
    SyncRequest,
)
from .outbox_client import HttpOutboxClient, OutboxClient
from .projector import MLProjector
from .settings import MLSettings, load_settings

logger = logging.getLogger(__name__)


async def _poll_forever(app: FastAPI) -> None:
    stop_event: asyncio.Event = app.state.poller_stop_event
    settings: MLSettings = app.state.settings
    projector: MLProjector = app.state.projector

    while not stop_event.is_set():
        try:
            await projector.sync_from_outbox(mode="poll", batch_size=settings.default_batch_size)
        except Exception:
            logger.exception("Background ML poll cycle failed.")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.poll_interval_sec)
        except TimeoutError:
            continue



def _resolve_projector(request: Request) -> MLProjector:
    projector = getattr(request.app.state, "projector", None)
    if projector is None:
        raise HTTPException(status_code=503, detail="ML projector is not initialized.")
    return projector



def _resolve_index_store(request: Request) -> RecommendationIndexStore:
    index_store = getattr(request.app.state, "index_store", None)
    if index_store is None:
        raise HTTPException(status_code=503, detail="ML index store is not initialized.")
    return index_store



def _resolve_projects(
    *,
    request_projects: list[ProjectPayload],
    index_store: RecommendationIndexStore,
) -> tuple[list[ProjectPayload], str]:
    if index_store.has_indexed_projects():
        return index_store.list_projects(), "outbox"
    return request_projects, "request"



def _rank_from_query(
    *,
    projects: list[ProjectPayload],
    query: str,
    limit: int,
    index_store: RecommendationIndexStore,
) -> RankedResponse:
    ranked = index_store.rank_projects(
        projects=projects,
        query_tokens=index_store._tokenize(query),  # noqa: SLF001 - central tokenizer
        limit=limit,
    )
    return RankedResponse(items=ranked)



def _parse_embedded_events(events: list[dict[str, Any]]) -> list[OutboxEvent]:
    parsed: list[OutboxEvent] = []
    for raw_event in events:
        try:
            parsed.append(OutboxEvent.model_validate(raw_event))
        except Exception:
            continue
    return parsed



def create_app(
    *,
    settings: MLSettings | None = None,
    index_store: RecommendationIndexStore | None = None,
    outbox_client: OutboxClient | None = None,
) -> FastAPI:
    resolved_settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved_index_store = index_store or RecommendationIndexStore(
            consumer=resolved_settings.outbox_consumer,
            state_path=resolved_settings.index_state_path,
        )
        resolved_outbox_client = outbox_client or HttpOutboxClient(
            base_url=resolved_settings.outbox_base_url,
            consumer=resolved_settings.outbox_consumer,
            timeout_sec=resolved_settings.outbox_timeout_sec,
            auth_header=resolved_settings.outbox_auth_header,
        )

        app.state.settings = resolved_settings
        app.state.index_store = resolved_index_store
        app.state.projector = MLProjector(
            index_store=resolved_index_store,
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

    app = FastAPI(title="Digital Student Assistant ML Service", lifespan=lifespan)

    @app.get("/")
    async def read_root() -> dict[str, str]:
        return {"service": "ml", "mode": "stub-heuristic"}

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "ml"}

    @app.get("/ready")
    async def readiness_check(request: Request) -> dict[str, Any]:
        projector = _resolve_projector(request)
        index_store = _resolve_index_store(request)

        outbox_status = "ok"
        checkpoint: dict[str, Any] | None = None
        try:
            checkpoint = await projector.read_checkpoint()
        except Exception as exc:
            outbox_status = f"error:{exc.__class__.__name__}"

        summary = index_store.get_state_summary(consumer=request.app.state.settings.outbox_consumer)
        status = "ok" if outbox_status == "ok" else "degraded"
        return {
            "status": status,
            "service": "ml",
            "mode": "stub-heuristic",
            "outbox": outbox_status,
            "consumer": request.app.state.settings.outbox_consumer,
            "projects_indexed": summary["projects_indexed"],
            "reindex_requests": summary["reindex_requests"],
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

    @app.post("/search", response_model=RankedResponse)
    async def search(payload: SearchRequest, request: Request) -> RankedResponse:
        index_store = _resolve_index_store(request)
        projects, _ = _resolve_projects(request_projects=payload.projects, index_store=index_store)
        return _rank_from_query(
            projects=projects,
            query=payload.query,
            limit=payload.limit,
            index_store=index_store,
        )

    @app.post("/recommendations", response_model=RankedResponse)
    async def recommendations(payload: RecommendationRequest, request: Request) -> RankedResponse:
        index_store = _resolve_index_store(request)
        projects, _ = _resolve_projects(request_projects=payload.projects, index_store=index_store)
        interests = " ".join(payload.interests)
        return _rank_from_query(
            projects=projects,
            query=interests,
            limit=payload.limit,
            index_store=index_store,
        )

    @app.post("/reindex", response_model=ReindexResponse)
    async def reindex(payload: ReindexRequest, request: Request) -> ReindexResponse:
        index_store = _resolve_index_store(request)
        manual_count = index_store.mark_reindex_requested(reason=payload.reason)
        direct_events = _parse_embedded_events(payload.events)
        if direct_events:
            projector = _resolve_projector(request)
            projector.project_events(direct_events)
        return ReindexResponse(reindex_requests=manual_count, status="accepted")

    return app


app = create_app()
