from pathlib import Path

from apps.projects.importers import default_epp_xlsx_path, import_epp_xlsx
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Import file-native EPP and vacancy data from XLSX."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(default_epp_xlsx_path()),
            help="Path to the EPP.xlsx file.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"]).expanduser().resolve()
        if not path.exists():
            raise CommandError(f"EPP.xlsx was not found: {path}")
        try:
            stats = import_epp_xlsx(path)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            "EPP import completed: "
            f"epp_created={stats.epp_created}, "
            f"epp_updated={stats.epp_updated}, "
            f"projects_created={stats.projects_created}, "
            f"projects_updated={stats.projects_updated}, "
            f"skipped={stats.skipped}, "
            f"errors={stats.errors}, "
            f"warnings={stats.warnings}"
        )
