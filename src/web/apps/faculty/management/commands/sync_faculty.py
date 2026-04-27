from apps.faculty.services import sync_faculty
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Synchronize faculty mirror data from the external faculty service."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--person-id", type=int, default=None)
        parser.add_argument(
            "--full",
            action="store_true",
            help="Sync all available faculty records. This is the default without --limit.",
        )

    def handle(self, *args, **options):
        stats = sync_faculty(limit=options["limit"], person_id=options["person_id"])
        self.stdout.write(
            self.style.SUCCESS(
                "faculty sync completed: "
                f"persons_seen={stats.persons_seen}, "
                f"persons_changed={stats.persons_changed}, "
                f"publications_seen={stats.publications_seen}, "
                f"publications_changed={stats.publications_changed}, "
                f"courses_seen={stats.courses_seen}, "
                f"courses_changed={stats.courses_changed}, "
                f"matches_changed={stats.matches_changed}"
            )
        )
