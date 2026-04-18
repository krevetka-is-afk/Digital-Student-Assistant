import re
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Digital Student Assistant ML Stub")

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_+#.-]+")
INDEX_STATE: dict[str, Any] = {
    "reindex_requests": 0,
    "last_payload": None,
}


class ProjectPayload(BaseModel):
    id: int
    title: str = ""
    description: str = ""
    tech_tags: list[str] = Field(default_factory=list)
    supervisor_name: str = ""
    source_type: str = ""


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    projects: list[ProjectPayload] = Field(default_factory=list)


class RecommendationRequest(BaseModel):
    interests: list[str] = Field(default_factory=list)
    limit: int = 10
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


def _tokenize(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value or "")}


def _project_text(project: ProjectPayload) -> str:
    return " ".join(
        [
            project.title,
            project.description,
            " ".join(project.tech_tags),
            project.supervisor_name,
            project.source_type,
        ]
    )


def _rank_projects(
    projects: list[ProjectPayload], query_tokens: set[str], limit: int
) -> list[RankedItem]:
    ranked: list[RankedItem] = []
    for project in projects:
        tokens = _tokenize(_project_text(project))
        overlap = query_tokens & tokens
        score = float(len(overlap))
        if score <= 0:
            continue
        ranked.append(
            RankedItem(
                project_id=project.id,
                score=score,
                reason="matched: " + ", ".join(sorted(overlap)[:5]),
            )
        )
    ranked.sort(key=lambda item: (-item.score, item.project_id))
    return ranked[:limit]


@app.get("/")
async def read_root():
    return {"service": "ml", "mode": "stub"}


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ml"}


@app.get("/ready")
async def readiness_check():
    return {
        "status": "ok",
        "service": "ml",
        "mode": "stub-heuristic",
        "reindex_requests": INDEX_STATE["reindex_requests"],
    }


@app.post("/search", response_model=RankedResponse)
async def search(payload: SearchRequest):
    return RankedResponse(
        items=_rank_projects(payload.projects, _tokenize(payload.query), payload.limit)
    )


@app.post("/recommendations", response_model=RankedResponse)
async def recommendations(payload: RecommendationRequest):
    interests = " ".join(payload.interests)
    return RankedResponse(
        items=_rank_projects(payload.projects, _tokenize(interests), payload.limit)
    )


@app.post("/reindex")
async def reindex(payload: ReindexRequest):
    INDEX_STATE["reindex_requests"] += 1
    INDEX_STATE["last_payload"] = payload.model_dump()
    return {
        "status": "accepted",
        "service": "ml",
        "mode": "stub-heuristic",
        "reindex_requests": INDEX_STATE["reindex_requests"],
    }
