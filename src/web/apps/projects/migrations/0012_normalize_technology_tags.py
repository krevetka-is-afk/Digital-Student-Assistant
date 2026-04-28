import re

from django.db import migrations

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_tag(value):
    return _WHITESPACE_RE.sub(" ", str(value).strip().lower())


def _normalize_tags(values):
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []

    normalized = []
    seen = set()
    for raw_value in values:
        tag = _normalize_tag(raw_value)
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


def normalize_project_tags(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    for project in Project.objects.only("id", "tech_tags").iterator():
        normalized_tags = _normalize_tags(project.tech_tags)
        if normalized_tags != project.tech_tags:
            project.tech_tags = normalized_tags
            project.save(update_fields=["tech_tags"])


def normalize_initiative_tags(apps, schema_editor):
    InitiativeProposal = apps.get_model("projects", "InitiativeProposal")
    for proposal in InitiativeProposal.objects.only("id", "tech_tags").iterator():
        normalized_tags = _normalize_tags(proposal.tech_tags)
        if normalized_tags != proposal.tech_tags:
            proposal.tech_tags = normalized_tags
            proposal.save(update_fields=["tech_tags"])


def normalize_submission_snapshots(apps, schema_editor):
    InitiativeProposalSubmission = apps.get_model("projects", "InitiativeProposalSubmission")
    for submission in InitiativeProposalSubmission.objects.only("id", "snapshot").iterator():
        snapshot = submission.snapshot if isinstance(submission.snapshot, dict) else {}
        if "tech_tags" not in snapshot:
            continue
        normalized_tags = _normalize_tags(snapshot.get("tech_tags"))
        if normalized_tags == snapshot.get("tech_tags"):
            continue
        snapshot["tech_tags"] = normalized_tags
        submission.snapshot = snapshot
        submission.save(update_fields=["snapshot"])


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0011_initiativeproposal_initiativeproposalsubmission_and_more"),
    ]

    operations = [
        migrations.RunPython(normalize_project_tags, migrations.RunPython.noop),
        migrations.RunPython(normalize_initiative_tags, migrations.RunPython.noop),
        migrations.RunPython(normalize_submission_snapshots, migrations.RunPython.noop),
    ]
