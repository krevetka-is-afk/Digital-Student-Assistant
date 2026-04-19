from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from .models import OutboxEvent, ProjectPayload, RankedItem

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_+#.-]+")
CATALOG_PROJECT_STATUSES = {"published", "staffed"}


@dataclass(slots=True)
class IndexedProject:
    id: int
    title: str = ""
    description: str = ""
    tech_tags: list[str] = field(default_factory=list)
    supervisor_name: str = ""
    source_type: str = ""
    status: str = "published"

    def to_payload(self) -> ProjectPayload:
        return ProjectPayload(
            id=self.id,
            title=self.title,
            description=self.description,
            tech_tags=list(self.tech_tags),
            supervisor_name=self.supervisor_name,
            source_type=self.source_type,
            status=self.status,
        )


class RecommendationIndexStore:
    def __init__(self, *, consumer: str, state_path: str | None = None):
        self._consumer = consumer
        self._state_path = Path(state_path) if state_path else None
        self._lock = RLock()
        self._projects: dict[int, IndexedProject] = {}
        self._profiles: dict[str, dict[str, Any]] = {}
        self._checkpoint_by_consumer: dict[str, int] = {consumer: 0}
        self._reindex_requests = 0
        self._last_reindex_reason: str | None = None
        self._last_event_id = 0
        self._last_event_at: str | None = None
        self._load()

    def _load(self) -> None:
        if self._state_path is None or not self._state_path.exists():
            return
        snapshot = json.loads(self._state_path.read_text())
        self._projects = {
            int(item["id"]): IndexedProject(
                id=int(item["id"]),
                title=str(item.get("title") or ""),
                description=str(item.get("description") or ""),
                tech_tags=[str(tag) for tag in item.get("tech_tags") or [] if str(tag).strip()],
                supervisor_name=str(item.get("supervisor_name") or ""),
                source_type=str(item.get("source_type") or ""),
                status=str(item.get("status") or "published").strip().lower() or "published",
            )
            for item in snapshot.get("projects") or []
        }
        self._profiles = {
            str(key): value for key, value in (snapshot.get("profiles") or {}).items()
        }
        self._checkpoint_by_consumer = {
            str(key): int(value) for key, value in (snapshot.get("checkpoints") or {}).items()
        } or {self._consumer: 0}
        self._reindex_requests = int(snapshot.get("reindex_requests") or 0)
        self._last_reindex_reason = snapshot.get("last_reindex_reason")
        self._last_event_id = int(snapshot.get("last_event_id") or 0)
        self._last_event_at = snapshot.get("last_event_at")

    def _snapshot(self) -> dict[str, Any]:
        return {
            "projects": [project.to_payload().model_dump() for project in self._projects.values()],
            "profiles": self._profiles,
            "checkpoints": self._checkpoint_by_consumer,
            "reindex_requests": self._reindex_requests,
            "last_reindex_reason": self._last_reindex_reason,
            "last_event_id": self._last_event_id,
            "last_event_at": self._last_event_at,
        }

    def _persist(self) -> None:
        if self._state_path is None:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._state_path.with_suffix(f"{self._state_path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(self._snapshot(), ensure_ascii=False, indent=2, sort_keys=True)
        )
        tmp_path.replace(self._state_path)

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        return {token.lower() for token in TOKEN_RE.findall(value or "")}

    @staticmethod
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

    @staticmethod
    def _normalize_tags(raw_tags: object) -> list[str]:
        if not isinstance(raw_tags, list):
            return []
        return [str(tag).strip() for tag in raw_tags if str(tag).strip()]

    @staticmethod
    def _to_event_timestamp(event: OutboxEvent) -> str:
        if event.created_at is not None:
            return event.created_at.astimezone(UTC).isoformat()
        return datetime.now(tz=UTC).isoformat()

    def has_indexed_projects(self) -> bool:
        with self._lock:
            return bool(self._projects)

    def list_projects(self) -> list[ProjectPayload]:
        with self._lock:
            return [project.to_payload() for project in self._projects.values()]

    def set_checkpoint_mirror(self, *, consumer: str, last_acked_event_id: int) -> None:
        with self._lock:
            self._checkpoint_by_consumer[consumer] = int(last_acked_event_id)
            self._persist()

    def mark_reindex_requested(self, *, reason: str) -> int:
        with self._lock:
            self._reindex_requests += 1
            self._last_reindex_reason = reason
            self._persist()
            return self._reindex_requests

    def get_state_summary(self, *, consumer: str) -> dict[str, Any]:
        with self._lock:
            return {
                "projects_indexed": len(self._projects),
                "profiles_indexed": len(self._profiles),
                "reindex_requests": self._reindex_requests,
                "last_reindex_reason": self._last_reindex_reason,
                "last_event_id": self._last_event_id,
                "last_event_at": self._last_event_at,
                "checkpoint_mirror": {
                    "consumer": consumer,
                    "last_acked_event_id": self._checkpoint_by_consumer.get(consumer, 0),
                },
            }

    def _upsert_project(self, *, aggregate_id: str, payload: dict[str, Any]) -> None:
        project_id_raw = payload.get("pk") or payload.get("id") or aggregate_id
        try:
            project_id = int(project_id_raw)
        except (TypeError, ValueError):
            return

        status = str(payload.get("status") or "published").strip().lower() or "published"
        if status not in CATALOG_PROJECT_STATUSES:
            self._projects.pop(project_id, None)
            return

        self._projects[project_id] = IndexedProject(
            id=project_id,
            title=str(payload.get("title") or payload.get("vacancy_title") or ""),
            description=str(payload.get("description") or ""),
            tech_tags=self._normalize_tags(payload.get("tech_tags")),
            supervisor_name=str(payload.get("supervisor_name") or ""),
            source_type=str(payload.get("source_type") or ""),
            status=status,
        )

    def _upsert_profile(self, *, aggregate_id: str, payload: dict[str, Any]) -> None:
        profile_id = str(payload.get("id") or aggregate_id).strip()
        if not profile_id:
            return
        interests = self._normalize_tags(payload.get("interests"))
        self._profiles[profile_id] = {
            "id": profile_id,
            "role": str(payload.get("role") or ""),
            "interests": interests,
            "favorite_project_ids": [
                int(project_id)
                for project_id in payload.get("favorite_project_ids") or []
                if str(project_id).isdigit()
            ],
        }

    def project_event(self, event: OutboxEvent) -> None:
        with self._lock:
            aggregate_type = event.aggregate_type.lower().strip()
            payload = event.payload or {}

            if aggregate_type == "project":
                self._upsert_project(aggregate_id=event.aggregate_id, payload=payload)
            elif aggregate_type == "user_profile":
                self._upsert_profile(aggregate_id=event.aggregate_id, payload=payload)
            elif event.event_type == "recs.reindex_requested":
                self._reindex_requests += 1
                self._last_reindex_reason = str(payload.get("reason") or "manual")

            if event.id is not None:
                self._last_event_id = max(self._last_event_id, int(event.id))
            self._last_event_at = self._to_event_timestamp(event)
            self._persist()

    def rank_projects(
        self,
        *,
        projects: list[ProjectPayload],
        query_tokens: set[str],
        limit: int,
    ) -> list[RankedItem]:
        ranked: list[RankedItem] = []
        for project in projects:
            tokens = self._tokenize(self._project_text(project))
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
