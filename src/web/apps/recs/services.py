from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Iterable, TypedDict, cast

import requests
from apps.projects.models import Project, ProjectStatus

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_+#.-]+")
ML_SEARCH_PATH = "/search"
ML_RECOMMENDATIONS_PATH = "/recommendations"
ML_GATEWAY_SEMANTIC_MODE = "semantic"
ML_GATEWAY_KEYWORD_FALLBACK_MODE = "keyword-fallback"
ML_DEFAULT_TIMEOUT_SECONDS = 2.5
ML_DEFAULT_REASON = "semantic match"

logger = logging.getLogger(__name__)


class MLRankedItem(TypedDict):
    project_id: int
    score: float
    reason: str


@dataclass(frozen=True)
class _RemoteCallResult:
    mode: str
    items: list[MLRankedItem]
    fallback_reason: str | None = None


def _tokenize(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value or "")}


def _project_text(project: Project) -> str:
    parts: list[str] = [
        project.title or "",
        project.description or "",
        project.vacancy_title or "",
        project.thesis_title or "",
        project.implementation_features or "",
        project.selection_criteria or "",
        " ".join(project.get_tags_list()),
    ]
    return " ".join(parts)


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


def _project_payload(project: Project) -> dict[str, object]:
    return {
        "id": project.pk,
        "title": project.title,
        "description": project.description,
        "tech_tags": project.get_tags_list(),
        "supervisor_name": project.supervisor_name,
        "source_type": project.source_type,
    }


def _ml_timeout_seconds() -> float:
    raw_timeout = os.getenv("ML_SERVICE_TIMEOUT", str(ML_DEFAULT_TIMEOUT_SECONDS))
    try:
        parsed_timeout = float(raw_timeout)
    except (TypeError, ValueError):
        return ML_DEFAULT_TIMEOUT_SECONDS
    if parsed_timeout <= 0:
        return ML_DEFAULT_TIMEOUT_SECONDS
    return parsed_timeout


def _normalize_remote_items(items: object) -> list[MLRankedItem] | None:
    if not isinstance(items, list):
        return None
    normalized: list[MLRankedItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_dict = cast(dict[str, object], item)
        project_id_raw = item_dict.get("project_id")
        try:
            project_id = int(cast(int | str, project_id_raw))
        except (TypeError, ValueError):
            continue
        score_raw = item_dict.get("score", 0)
        try:
            score = float(cast(int | float | str, score_raw))
        except (TypeError, ValueError):
            score = 0.0
        reason_raw = item_dict.get("reason")
        reason = str(reason_raw) if reason_raw is not None else ML_DEFAULT_REASON
        normalized.append({"project_id": project_id, "score": score, "reason": reason})
    return normalized


def _call_remote_ml(
    path: str, payload: dict[str, object], *, operation: str
) -> _RemoteCallResult:
    base_url = os.getenv("ML_SERVICE_URL", "").rstrip("/")
    if not base_url:
        logger.info(
            "recs.gateway mode=%s operation=%s reason=ml_service_not_configured",
            ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            operation,
        )
        return _RemoteCallResult(
            mode=ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            items=[],
            fallback_reason="ml_service_not_configured",
        )

    try:
        response = requests.post(
            f"{base_url}{path}",
            json=payload,
            timeout=_ml_timeout_seconds(),
        )
        response.raise_for_status()
        body = response.json()
    except requests.Timeout:
        logger.warning(
            "recs.gateway mode=%s operation=%s reason=ml_timeout",
            ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            operation,
        )
        return _RemoteCallResult(
            mode=ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            items=[],
            fallback_reason="ml_timeout",
        )
    except requests.RequestException:
        logger.warning(
            "recs.gateway mode=%s operation=%s reason=ml_request_error",
            ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            operation,
            exc_info=True,
        )
        return _RemoteCallResult(
            mode=ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            items=[],
            fallback_reason="ml_request_error",
        )
    except ValueError:
        logger.warning(
            "recs.gateway mode=%s operation=%s reason=ml_invalid_json",
            ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            operation,
        )
        return _RemoteCallResult(
            mode=ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            items=[],
            fallback_reason="ml_invalid_json",
        )

    if not isinstance(body, dict):
        logger.warning(
            "recs.gateway mode=%s operation=%s reason=ml_invalid_body",
            ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            operation,
        )
        return _RemoteCallResult(
            mode=ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            items=[],
            fallback_reason="ml_invalid_body",
        )

    raw_items = body.get("items")
    items = _normalize_remote_items(raw_items)
    if items is None:
        logger.warning(
            "recs.gateway mode=%s operation=%s reason=ml_invalid_items",
            ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            operation,
        )
        return _RemoteCallResult(
            mode=ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            items=[],
            fallback_reason="ml_invalid_items",
        )
    if isinstance(raw_items, list) and raw_items and not items:
        logger.warning(
            "recs.gateway mode=%s operation=%s reason=ml_invalid_items",
            ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            operation,
        )
        return _RemoteCallResult(
            mode=ML_GATEWAY_KEYWORD_FALLBACK_MODE,
            items=[],
            fallback_reason="ml_invalid_items",
        )

    logger.info(
        "recs.gateway mode=%s operation=%s remote_items=%s",
        ML_GATEWAY_SEMANTIC_MODE,
        operation,
        len(items),
    )
    return _RemoteCallResult(mode=ML_GATEWAY_SEMANTIC_MODE, items=items)


def _hydrate_remote_items(
    *, projects: list[Project], items: list[MLRankedItem]
) -> list[dict[str, object]]:
    project_by_id = {project.pk: project for project in projects}
    hydrated: list[dict[str, object]] = []
    for item in items:
        project = project_by_id.get(item["project_id"])
        if project is None:
            continue
        hydrated.append(
            {
                "project": project,
                "score": item["score"],
                "reason": item["reason"],
            }
        )
    return hydrated


def search_projects(query: str, *, limit: int = 10) -> tuple[str, list[dict[str, object]]]:
    projects = _published_projects()
    remote_result = _call_remote_ml(
        ML_SEARCH_PATH,
        {
            "query": query,
            "limit": limit,
            "projects": [_project_payload(project) for project in projects],
        },
        operation="search",
    )
    if remote_result.mode == ML_GATEWAY_SEMANTIC_MODE:
        return remote_result.mode, _hydrate_remote_items(
            projects=projects,
            items=remote_result.items,
        )

    ranked = _heuristic_rank(
        projects=projects,
        query_tokens=_tokenize(query),
        limit=limit,
        reason_label="local-search match",
    )
    logger.info(
        "recs.gateway mode=%s operation=search reason=%s",
        ML_GATEWAY_KEYWORD_FALLBACK_MODE,
        remote_result.fallback_reason or "keyword_overlap",
    )
    return ML_GATEWAY_KEYWORD_FALLBACK_MODE, ranked


def recommend_projects(
    interests: list[str], *, limit: int = 10
) -> tuple[str, list[dict[str, object]]]:
    projects = _published_projects()
    remote_result = _call_remote_ml(
        ML_RECOMMENDATIONS_PATH,
        {
            "interests": interests,
            "limit": limit,
            "projects": [_project_payload(project) for project in projects],
        },
        operation="recommendations",
    )
    if remote_result.mode == ML_GATEWAY_SEMANTIC_MODE:
        return remote_result.mode, _hydrate_remote_items(
            projects=projects,
            items=remote_result.items,
        )

    query_tokens = _tokenize(" ".join(interests))
    ranked = _heuristic_rank(
        projects=projects,
        query_tokens=query_tokens,
        limit=limit,
        reason_label="interest overlap",
    )
    logger.info(
        "recs.gateway mode=%s operation=recommendations reason=%s",
        ML_GATEWAY_KEYWORD_FALLBACK_MODE,
        remote_result.fallback_reason or "interest_overlap",
    )
    return ML_GATEWAY_KEYWORD_FALLBACK_MODE, ranked
