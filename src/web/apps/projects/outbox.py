from __future__ import annotations

from typing import Any

from apps.outbox.services import emit_event
from django.utils import timezone

from .models import Project


def _isoformat(value) -> str | None:
    return value.isoformat() if value else None


def build_project_outbox_payload(project: Project) -> dict[str, Any]:
    """Build the project payload consumed by ML and graph projectors.

    Automatic outbox emission is model-signal based, so normal ``save()`` and
    ``delete()`` calls are covered. Django ``QuerySet.update()`` and
    ``bulk_update()`` bypass model signals and therefore do not emit events.
    """

    return {
        "id": project.pk,
        "pk": project.pk,
        "title": project.title,
        "description": project.description,
        "tech_tags": project.tech_tags or [],
        "supervisor_name": project.supervisor_name,
        "supervisor_email": project.supervisor_email,
        "source_type": project.source_type,
        "status": project.status,
        "created_at": _isoformat(project.created_at),
        "updated_at": _isoformat(project.updated_at),
    }


def emit_project_changed(project: Project) -> None:
    if project.pk is None:
        return
    updated_at = project.updated_at or timezone.now()
    emit_project_changed_snapshot(
        project_id=project.pk,
        payload=build_project_outbox_payload(project),
        updated_at=updated_at,
    )


def emit_project_changed_snapshot(*, project_id: int, payload: dict[str, Any], updated_at) -> None:
    emit_event(
        event_type="project.changed",
        aggregate_type="project",
        aggregate_id=project_id,
        payload=payload,
        idempotency_key=f"project.changed:{project_id}:{updated_at.isoformat()}:save",
    )


def build_project_deleted_payload(project: Project, *, deleted_at) -> dict[str, Any]:
    payload = build_project_outbox_payload(project)
    payload.update(
        {
            "status": "deleted",
            "tombstone": True,
            "deleted_at": deleted_at.isoformat(),
        }
    )
    return payload


def emit_project_deleted(project: Project, *, deleted_at) -> None:
    if project.pk is None:
        return
    idempotency_timestamp = project.updated_at or deleted_at
    emit_project_deleted_snapshot(
        project_id=project.pk,
        payload=build_project_deleted_payload(project, deleted_at=deleted_at),
        idempotency_timestamp=idempotency_timestamp,
    )


def emit_project_deleted_snapshot(
    *,
    project_id: int,
    payload: dict[str, Any],
    idempotency_timestamp,
) -> None:
    emit_event(
        event_type="project.deleted",
        aggregate_type="project",
        aggregate_id=project_id,
        payload=payload,
        idempotency_key=f"project.deleted:{project_id}:{idempotency_timestamp.isoformat()}:delete",
    )
