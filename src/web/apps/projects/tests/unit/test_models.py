from uuid import uuid4

import pytest
from apps.outbox.models import OutboxEvent
from apps.projects.models import (
    Project,
    ProjectSourceType,
    ProjectStatus,
    Technology,
    TechnologyStatus,
)


def test_project_defaults():
    project = Project(title="Data platform")

    assert project.status == ProjectStatus.DRAFT
    assert project.source_type == ProjectSourceType.MANUAL
    assert project.tech_tags == []


def test_technology_normalizes_name_on_save():
    suffix = uuid4().hex[:8]
    technology = Technology.objects.create(name=f" Test Tech {suffix} ")

    assert technology.name == f"test tech {suffix}"
    assert technology.normalized_name == f"test tech {suffix}"
    assert technology.status == TechnologyStatus.PENDING


def test_project_save_links_normalized_technology_directory_entries():
    project = Project.objects.create(
        title="Directory sync",
        tech_tags=[" Python ", "python", "React  Native"],
    )

    assert project.tech_tags == ["python", "react native"]
    assert list(
        project.technologies.order_by("normalized_name").values_list("normalized_name", flat=True)
    ) == [
        "python",
        "react native",
    ]
    assert Technology.objects.filter(normalized_name="python").exists()


def test_project_save_emits_single_changed_outbox_event():
    project = Project.objects.create(
        title=f"Outbox direct create {uuid4().hex[:8]}",
        description="initial",
        tech_tags=["Python"],
        supervisor_name="Dr Supervisor",
        supervisor_email="supervisor@example.test",
        status=ProjectStatus.PUBLISHED,
    )

    events = OutboxEvent.objects.filter(
        event_type="project.changed",
        aggregate_type="project",
        aggregate_id=str(project.pk),
    )
    assert events.count() == 1
    event = events.get()
    assert event.payload["pk"] == project.pk
    assert event.payload["id"] == project.pk
    assert event.payload["title"] == project.title
    assert event.payload["description"] == "initial"
    assert event.payload["tech_tags"] == ["python"]
    assert event.payload["supervisor_name"] == "Dr Supervisor"
    assert event.payload["supervisor_email"] == "supervisor@example.test"
    assert event.payload["source_type"] == ProjectSourceType.MANUAL
    assert event.payload["status"] == ProjectStatus.PUBLISHED
    assert event.payload["updated_at"] == project.updated_at.isoformat()

    OutboxEvent.objects.filter(aggregate_id=str(project.pk)).delete()
    project.description = "updated"
    project.save(update_fields=["description", "updated_at"])

    events = OutboxEvent.objects.filter(
        event_type="project.changed",
        aggregate_type="project",
        aggregate_id=str(project.pk),
    )
    assert events.count() == 1
    assert events.get().payload["description"] == "updated"


def test_project_delete_emits_single_deleted_outbox_event():
    project = Project.objects.create(title=f"Outbox direct delete {uuid4().hex[:8]}")
    project_pk = project.pk
    OutboxEvent.objects.filter(aggregate_id=str(project_pk)).delete()

    project.delete()

    events = OutboxEvent.objects.filter(
        event_type="project.deleted",
        aggregate_type="project",
        aggregate_id=str(project_pk),
    )
    assert events.count() == 1
    event = events.get()
    assert event.payload["pk"] == project_pk
    assert event.payload["status"] == "deleted"
    assert event.payload["tombstone"] is True
    assert event.payload["deleted_at"] is not None


def test_project_delete_emits_deleted_outbox_event_when_transaction_commits():
    from django.db import transaction

    project = Project.objects.create(title=f"Outbox atomic delete {uuid4().hex[:8]}")
    project_pk = project.pk
    OutboxEvent.objects.filter(aggregate_id=str(project_pk)).delete()

    with transaction.atomic():
        project.delete()

    events = OutboxEvent.objects.filter(
        event_type="project.deleted",
        aggregate_type="project",
        aggregate_id=str(project_pk),
    )
    assert events.count() == 1
    assert events.get().payload["pk"] == project_pk


def test_project_delete_does_not_emit_outbox_event_when_transaction_rolls_back():
    from django.db import transaction

    project = Project.objects.create(title=f"Outbox rollback delete {uuid4().hex[:8]}")
    project_pk = project.pk
    OutboxEvent.objects.filter(aggregate_id=str(project_pk)).delete()

    with pytest.raises(RuntimeError):
        with transaction.atomic():
            project.delete()
            raise RuntimeError("rollback")

    assert Project.objects.filter(pk=project_pk).exists()
    assert not OutboxEvent.objects.filter(
        event_type="project.deleted",
        aggregate_id=str(project_pk),
    ).exists()


def test_project_save_does_not_emit_outbox_event_when_transaction_rolls_back():
    title = f"Rolled back outbox {uuid4().hex[:8]}"

    with pytest.raises(RuntimeError):
        from django.db import transaction

        with transaction.atomic():
            Project.objects.create(title=title)
            raise RuntimeError("rollback")

    assert not Project.objects.filter(title=title).exists()
    assert not OutboxEvent.objects.filter(payload__title=title).exists()
