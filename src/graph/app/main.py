import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

DATA_DIR = Path(os.getenv("GRAPH_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE = DATA_DIR / "checkpoint.json"


class GraphEvent(BaseModel):
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ReplayRequest(BaseModel):
    events: list[GraphEvent] = Field(default_factory=list)


STATE: dict[str, Any] = {
    "last_event_id": 0,
    "nodes": {
        "project": set(),
        "student": set(),
        "supervisor": set(),
        "tag": set(),
        "application": set(),
    },
    "edges": [],
}


def _load_checkpoint() -> None:
    if not CHECKPOINT_FILE.exists():
        return
    payload = json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
    STATE["last_event_id"] = int(payload.get("last_event_id", 0))
    STATE["nodes"] = {key: set(values) for key, values in payload.get("nodes", {}).items()}
    STATE["edges"] = list(payload.get("edges", []))


def _persist_checkpoint() -> None:
    CHECKPOINT_FILE.write_text(
        json.dumps(
            {
                "last_event_id": STATE["last_event_id"],
                "nodes": {key: sorted(values) for key, values in STATE["nodes"].items()},
                "edges": STATE["edges"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _append_edge(edge_type: str, source: str, target: str) -> None:
    edge = {"type": edge_type, "source": source, "target": target}
    if edge not in STATE["edges"]:
        STATE["edges"].append(edge)


def _project_event(event: GraphEvent) -> None:
    payload = event.payload
    if event.aggregate_type == "project":
        project_id = str(payload.get("pk") or event.aggregate_id)
        STATE["nodes"]["project"].add(project_id)
        supervisor = payload.get("supervisor_email") or payload.get("supervisor_name")
        if supervisor:
            supervisor_id = str(supervisor)
            STATE["nodes"]["supervisor"].add(supervisor_id)
            _append_edge("SUPERVISED_BY", project_id, supervisor_id)
        for tag in payload.get("tech_tags", []):
            tag_id = str(tag)
            STATE["nodes"]["tag"].add(tag_id)
            _append_edge("TAGGED_WITH", project_id, tag_id)
    elif event.aggregate_type == "user_profile":
        student_id = str(payload.get("id") or event.aggregate_id)
        STATE["nodes"]["student"].add(student_id)
        for interest in payload.get("interests", []):
            tag_id = str(interest)
            STATE["nodes"]["tag"].add(tag_id)
            _append_edge("INTERESTED_IN", student_id, tag_id)
    elif event.aggregate_type == "application":
        application_id = str(payload.get("id") or event.aggregate_id)
        STATE["nodes"]["application"].add(application_id)
        applicant = payload.get("applicant_snapshot", {}) or {}
        applicant_id = applicant.get("id")
        if applicant_id is not None:
            student_id = str(applicant_id)
            STATE["nodes"]["student"].add(student_id)
            _append_edge("SUBMITTED", student_id, application_id)
        project = payload.get("project_snapshot", {}) or {}
        project_id = project.get("pk")
        if project_id is not None:
            STATE["nodes"]["project"].add(str(project_id))
            _append_edge("TARGETS", application_id, str(project_id))

    STATE["last_event_id"] += 1


@asynccontextmanager
async def lifespan(_: FastAPI):
    _load_checkpoint()
    yield


app = FastAPI(title="Digital Student Assistant Graph Projector", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "graph"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "graph",
        "checkpoint_file": str(CHECKPOINT_FILE),
        "last_event_id": STATE["last_event_id"],
    }


@app.get("/state")
async def state() -> dict[str, Any]:
    return {
        "last_event_id": STATE["last_event_id"],
        "nodes": {key: len(values) for key, values in STATE["nodes"].items()},
        "edges": len(STATE["edges"]),
    }


@app.post("/project")
async def project_events(payload: ReplayRequest) -> dict[str, Any]:
    for event in payload.events:
        _project_event(event)
    _persist_checkpoint()
    return {
        "status": "accepted",
        "processed": len(payload.events),
        "last_event_id": STATE["last_event_id"],
    }


@app.post("/replay")
async def replay(payload: ReplayRequest) -> dict[str, Any]:
    for event in payload.events:
        _project_event(event)
    _persist_checkpoint()
    return {
        "status": "accepted",
        "replayed": len(payload.events),
        "last_event_id": STATE["last_event_id"],
    }
