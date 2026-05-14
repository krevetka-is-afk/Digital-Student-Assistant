from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import Project
from .outbox import (
    build_project_deleted_payload,
    build_project_outbox_payload,
    emit_project_changed_snapshot,
    emit_project_deleted_snapshot,
)


@receiver(post_save, sender=Project, dispatch_uid="projects.emit_project_changed")
def schedule_project_changed_event(sender, instance: Project, raw: bool = False, **kwargs) -> None:
    if raw:
        return

    project_id = instance.pk
    if project_id is None:
        return
    updated_at = instance.updated_at or timezone.now()
    payload = build_project_outbox_payload(instance)

    transaction.on_commit(
        lambda: emit_project_changed_snapshot(
            project_id=project_id,
            payload=payload,
            updated_at=updated_at,
        )
    )


@receiver(pre_delete, sender=Project, dispatch_uid="projects.emit_project_deleted")
def schedule_project_deleted_event(sender, instance: Project, **kwargs) -> None:
    project_id = instance.pk
    if project_id is None:
        return
    deleted_at = timezone.now()
    idempotency_timestamp = instance.updated_at or deleted_at
    payload = build_project_deleted_payload(instance, deleted_at=deleted_at)

    transaction.on_commit(
        lambda: emit_project_deleted_snapshot(
            project_id=project_id,
            payload=payload,
            idempotency_timestamp=idempotency_timestamp,
        )
    )
