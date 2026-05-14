from __future__ import annotations

import json

from apps.outbox.models import OutboxEvent
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from django.core.management.base import BaseCommand
from django.utils import timezone

TESTER_SOURCE_REF = "outbox-tester"
TESTER_TITLE = "Outbox Tester"


class Command(BaseCommand):
    help = "Create or update the singleton Outbox Tester project through normal Project.save()."

    def handle(self, *args, **options):
        now = timezone.now()
        project, created = Project.objects.get_or_create(
            source_type=ProjectSourceType.MANUAL,
            source_ref=TESTER_SOURCE_REF,
            defaults={
                "title": TESTER_TITLE,
                "description": _description(tick=1, timestamp=now),
                "status": ProjectStatus.PUBLISHED,
                "tech_tags": ["outbox", "ml", "graph", "django"],
                "team_size": 2,
                "extra_data": {"outbox_tester": True, "tick": 1},
                "supervisor_name": "Outbox Demo",
                "supervisor_email": "outbox-demo@example.test",
            },
        )

        if not created:
            tick = int((project.extra_data or {}).get("tick") or 0) + 1
            project.title = TESTER_TITLE
            project.description = _description(tick=tick, timestamp=now)
            project.status = ProjectStatus.PUBLISHED
            project.tech_tags = ["outbox", "ml", "graph", "django"]
            project.team_size = 1 + (tick % 3)
            project.extra_data = {**(project.extra_data or {}), "outbox_tester": True, "tick": tick}
            project.supervisor_name = project.supervisor_name or "Outbox Demo"
            project.supervisor_email = project.supervisor_email or "outbox-demo@example.test"
            project.save(
                update_fields=[
                    "title",
                    "description",
                    "status",
                    "tech_tags",
                    "team_size",
                    "extra_data",
                    "supervisor_name",
                    "supervisor_email",
                    "updated_at",
                ]
            )

        latest_event = (
            OutboxEvent.objects.filter(
                event_type="project.changed",
                aggregate_type="project",
                aggregate_id=str(project.pk),
            )
            .order_by("-id")
            .first()
        )
        event_count = OutboxEvent.objects.filter(
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id=str(project.pk),
        ).count()
        payload = {
            "project_id": project.pk,
            "created": created,
            "status": project.status,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
            "latest_event_id": latest_event.id if latest_event else None,
            "event_count": event_count,
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _description(*, tick: int, timestamp) -> str:
    return (
        "Outbox tester heartbeat project. "
        f"Tick #{tick} generated at {timestamp.isoformat()}."
    )
