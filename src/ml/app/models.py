from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectPayload(BaseModel):
    id: int
    title: str = ""
    description: str = ""
    tech_tags: list[str] = Field(default_factory=list)
    supervisor_name: str = ""
    source_type: str = ""
    status: str = "published"


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=100)
    projects: list[ProjectPayload] = Field(default_factory=list)


class RecommendationRequest(BaseModel):
    interests: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)
    projects: list[ProjectPayload] = Field(default_factory=list)


class RankedItem(BaseModel):
    project_id: int
    score: float
    reason: str


class RankedResponse(BaseModel):
    mode: str = "stub-heuristic"
    items: list[RankedItem]


class ReindexRequest(BaseModel):
    reason: str = "manual"
    events: list[dict[str, Any]] = Field(default_factory=list)


class ReindexResponse(BaseModel):
    status: str
    service: str = "ml"
    mode: str = "stub-heuristic"
    reindex_requests: int


class OutboxEvent(BaseModel):
    id: int | None = None
    event_type: str
    aggregate_type: str
    aggregate_id: str
    source: str | None = None
    idempotency_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class ProjectRequest(BaseModel):
    events: list[OutboxEvent] = Field(default_factory=list)


class SyncRequest(BaseModel):
    batch_size: int | None = Field(default=None, ge=1, le=1000)


class ReplayRequest(BaseModel):
    replay_from_id: int | None = Field(default=None, ge=1)
    batch_size: int | None = Field(default=None, ge=1, le=1000)
    events: list[OutboxEvent] = Field(default_factory=list)
