import json
from io import StringIO

from apps.outbox.models import OutboxEvent
from apps.projects.management.commands.tick_outbox_tester import TESTER_SOURCE_REF, TESTER_TITLE
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from django.core.management import call_command


def _reset_tester_state():
    Project.objects.filter(
        source_type=ProjectSourceType.MANUAL,
        source_ref=TESTER_SOURCE_REF,
    ).delete()
    OutboxEvent.objects.filter(aggregate_type="project").delete()


def _run_tick() -> dict:
    stdout = StringIO()
    call_command("tick_outbox_tester", stdout=stdout)
    return json.loads(stdout.getvalue())


def test_tick_outbox_tester_creates_single_published_project_and_changed_event():
    _reset_tester_state()

    payload = _run_tick()

    project = Project.objects.get(
        source_type=ProjectSourceType.MANUAL,
        source_ref=TESTER_SOURCE_REF,
    )
    assert payload["project_id"] == project.pk
    assert payload["created"] is True
    assert payload["event_count"] == 1
    assert project.title == TESTER_TITLE
    assert project.status == ProjectStatus.PUBLISHED
    assert project.extra_data["outbox_tester"] is True
    assert project.extra_data["tick"] == 1
    assert project.tech_tags == ["outbox", "ml", "graph", "django"]
    assert OutboxEvent.objects.filter(
        event_type="project.changed",
        aggregate_type="project",
        aggregate_id=str(project.pk),
    ).count() == 1


def test_tick_outbox_tester_reuses_project_and_emits_one_changed_event_per_run():
    _reset_tester_state()

    first_payload = _run_tick()
    second_payload = _run_tick()

    project = Project.objects.get(
        source_type=ProjectSourceType.MANUAL,
        source_ref=TESTER_SOURCE_REF,
    )
    events = OutboxEvent.objects.filter(
        event_type="project.changed",
        aggregate_type="project",
        aggregate_id=str(project.pk),
    )
    assert first_payload["project_id"] == second_payload["project_id"] == project.pk
    assert second_payload["created"] is False
    assert second_payload["event_count"] == 2
    assert Project.objects.filter(
        source_type=ProjectSourceType.MANUAL,
        source_ref=TESTER_SOURCE_REF,
    ).count() == 1
    assert events.count() == 2
    assert project.status == ProjectStatus.PUBLISHED
    assert project.extra_data["tick"] == 2
    assert project.description.startswith("Outbox tester heartbeat project. Tick #2")
