from __future__ import annotations

import os
import re
from typing import Iterable

import requests
from apps.projects.models import Project, ProjectStatus

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_+#.-]+")


def _tokenize(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value or "")}


def _project_text(project: Project) -> str:
    return " ".join(
        [
            project.title or "",
            project.description or "",
            project.vacancy_title or "",
            project.thesis_title or "",
            project.implementation_features or "",
            project.selection_criteria or "",
            " ".join(project.get_tags_list()),
        ]
    )


def _heuristic_rank(
    *,
    projects: Iterable[Project],
    query_tokens: set[str],
    limit: int,
    reason_label: str,
) -> list[dict[str, object]]:
    ranked: list[dict[str, object]] = []
    for project in projects:
        project_tokens = _tokenize(_project_text(project))
        overlap = query_tokens & project_tokens
        score = float(len(overlap))
        if score <= 0:
            continue
        ranked.append(
            {
                "project": project,
                "score": score,
                "reason": f"{reason_label}: " + ", ".join(sorted(overlap)[:5]),
            }
        )
    ranked.sort(key=lambda item: (-float(item["score"]), item["project"].pk))
    return ranked[:limit]


def _published_projects() -> list[Project]:
    return list(
        Project.objects.filter(status__in=ProjectStatus.catalog_values()).select_related(
            "owner", "epp"
        )
    )


def _remote_ml_enabled() -> bool:
    return bool(os.getenv("ML_SERVICE_URL"))


def _project_payload(project: Project) -> dict[str, object]:
    return {
        "id": project.pk,
        "title": project.title,
        "description": project.description,
        "tech_tags": project.get_tags_list(),
        "supervisor_name": project.supervisor_name,
        "source_type": project.source_type,
    }


def _call_remote_ml(
    path: str, payload: dict[str, object]
) -> tuple[str, list[dict[str, object]]] | None:
    base_url = os.getenv("ML_SERVICE_URL", "").rstrip("/")
    if not base_url:
        return None
    timeout = float(os.getenv("ML_SERVICE_TIMEOUT", "2.5"))
    try:
        response = requests.post(f"{base_url}{path}", json=payload, timeout=timeout)
        response.raise_for_status()
        body = response.json()
    except Exception:
        return None
    return str(body.get("mode", "remote")), list(body.get("items", []))


def search_projects(query: str, *, limit: int = 10) -> tuple[str, list[dict[str, object]]]:
    projects = _published_projects()
    remote_result = _call_remote_ml(
        "/search",
        {
            "query": query,
            "limit": limit,
            "projects": [_project_payload(project) for project in projects],
        },
    )
    if remote_result is not None:
        mode, items = remote_result
        project_by_id = {project.pk: project for project in projects}
        hydrated: list[dict[str, object]] = []
        for item in items:
            project = project_by_id.get(int(item.get("project_id", 0)))
            if project is None:
                continue
            hydrated.append(
                {
                    "project": project,
                    "score": float(item.get("score", 0)),
                    "reason": str(item.get("reason", "")),
                }
            )
        return mode, hydrated
    ranked = _heuristic_rank(
        projects=projects,
        query_tokens=_tokenize(query),
        limit=limit,
        reason_label="local-search match",
    )
    return ("local-fallback", ranked)


def recommend_projects(
    interests: list[str], *, limit: int = 10
) -> tuple[str, list[dict[str, object]]]:
    projects = _published_projects()
    remote_result = _call_remote_ml(
        "/recommendations",
        {
            "interests": interests,
            "limit": limit,
            "projects": [_project_payload(project) for project in projects],
        },
    )
    if remote_result is not None:
        mode, items = remote_result
        project_by_id = {project.pk: project for project in projects}
        hydrated: list[dict[str, object]] = []
        for item in items:
            project = project_by_id.get(int(item.get("project_id", 0)))
            if project is None:
                continue
            hydrated.append(
                {
                    "project": project,
                    "score": float(item.get("score", 0)),
                    "reason": str(item.get("reason", "")),
                }
            )
        return mode, hydrated

    query_tokens = _tokenize(" ".join(interests))
    ranked = _heuristic_rank(
        projects=projects,
        query_tokens=query_tokens,
        limit=limit,
        reason_label="interest overlap",
    )
    return ("local-fallback", ranked)
