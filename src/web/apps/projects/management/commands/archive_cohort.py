from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.projects.models import Project, ProjectStatus


class Command(BaseCommand):
    help = (
        "Archive all active projects from a given academic year. "
        "Archived projects are hidden from the catalog but remain visible "
        "in students' application history."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "year",
            help='Academic year to archive, e.g. "2024-2025".',
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print which projects would be archived without making changes.",
        )

    def handle(self, *args, **options):
        year: str = options["year"].strip()
        dry_run: bool = options["dry_run"]

        if not year:
            raise CommandError("Academic year must not be empty.")

        archivable_statuses = (
            ProjectStatus.PUBLISHED,
            ProjectStatus.STAFFED,
            ProjectStatus.COMPLETED,
        )

        qs = Project.objects.filter(
            academic_year=year,
            status__in=archivable_statuses,
        ).order_by("pk")

        count = qs.count()
        if count == 0:
            self.stdout.write(
                self.style.WARNING(
                    f'No archivable projects found for academic year "{year}".'
                )
            )
            return

        self.stdout.write(f'Found {count} project(s) for academic year "{year}":')
        for p in qs:
            self.stdout.write(f"  [{p.status}] #{p.pk} {p.title}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        updated = qs.update(status=ProjectStatus.ARCHIVED)
        self.stdout.write(
            self.style.SUCCESS(
                f'Done: {updated} project(s) archived for academic year "{year}".'
            )
        )
