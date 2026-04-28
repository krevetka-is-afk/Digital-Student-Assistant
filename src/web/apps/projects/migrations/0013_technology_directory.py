import re

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

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


def _get_or_create_technology(Technology, tag, *, status="approved", created_by_id=None):
    normalized = _normalize_tag(tag)
    technology, created = Technology.objects.get_or_create(
        normalized_name=normalized,
        defaults={
            "name": normalized,
            "status": status,
            "created_by_id": created_by_id,
        },
    )
    if not created and status == "approved" and technology.status != "approved":
        technology.status = "approved"
        technology.save(update_fields=["status"])
    return technology


def populate_project_technologies(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Technology = apps.get_model("projects", "Technology")
    for project in Project.objects.only("id", "owner_id", "source_type", "tech_tags").iterator():
        normalized_tags = _normalize_tags(project.tech_tags)
        technologies = [
            _get_or_create_technology(
                Technology,
                tag,
                status="approved",
                created_by_id=project.owner_id,
            )
            for tag in normalized_tags
        ]
        project.technologies.set(technologies)


def populate_initiative_technologies(apps, schema_editor):
    InitiativeProposal = apps.get_model("projects", "InitiativeProposal")
    Technology = apps.get_model("projects", "Technology")
    for proposal in InitiativeProposal.objects.only("id", "owner_id", "tech_tags").iterator():
        technologies = [
            _get_or_create_technology(
                Technology,
                tag,
                status="pending",
                created_by_id=proposal.owner_id,
            )
            for tag in _normalize_tags(proposal.tech_tags)
        ]
        proposal.technologies.set(technologies)


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0012_normalize_technology_tags"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Technology",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Display technology name. Stored in normalized lowercase form.",
                        max_length=100,
                        verbose_name="Name",
                    ),
                ),
                (
                    "normalized_name",
                    models.CharField(
                        db_index=True,
                        help_text="Lowercase canonical technology key used for matching.",
                        max_length=100,
                        unique=True,
                        verbose_name="Normalized name",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("approved", "Approved"),
                            ("pending", "Pending"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="pending",
                        help_text="Moderation status for user- or customer-submitted technologies.",
                        max_length=20,
                        verbose_name="Status",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        verbose_name="Created at",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        verbose_name="Updated at",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who first suggested this technology, when known.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_technologies",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created by",
                    ),
                ),
            ],
            options={
                "verbose_name": "Technology",
                "verbose_name_plural": "Technologies",
                "ordering": ["normalized_name"],
            },
        ),
        migrations.AddField(
            model_name="project",
            name="technologies",
            field=models.ManyToManyField(
                blank=True,
                help_text="Canonical technology directory entries linked to this project.",
                related_name="projects",
                to="projects.technology",
                verbose_name="Technologies",
            ),
        ),
        migrations.AddField(
            model_name="initiativeproposal",
            name="technologies",
            field=models.ManyToManyField(
                blank=True,
                help_text="Canonical technology directory entries linked to this proposal.",
                related_name="initiative_proposals",
                to="projects.technology",
                verbose_name="Technologies",
            ),
        ),
        migrations.RunPython(populate_project_technologies, migrations.RunPython.noop),
        migrations.RunPython(populate_initiative_technologies, migrations.RunPython.noop),
    ]
