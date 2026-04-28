from pathlib import Path
from tempfile import NamedTemporaryFile

from apps.outbox.services import emit_event
from apps.projects.importers import default_epp_xlsx_path, import_epp_xlsx
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

from .models import ImportRun
from .serializers import ImportRunSerializer


def run_epp_xlsx_import(
    *,
    upload: UploadedFile | None = None,
    imported_by_id: int | None = None,
) -> ImportRun:
    source_name = Path(getattr(upload, "name", "")).name or default_epp_xlsx_path().name
    import_run = ImportRun.objects.create(
        source="xlsx",
        source_name=source_name,
        imported_by_id=imported_by_id,
        status="running",
    )
    path: Path | None = None
    try:
        if upload is not None:
            # The importer reads the archive directly, so the temp suffix stays fixed.
            with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
                for chunk in upload.chunks():
                    tmp_file.write(chunk)
                path = Path(tmp_file.name)
        else:
            path = default_epp_xlsx_path()

        stats = import_epp_xlsx(path)
        import_run.status = "completed"
        import_run.stats = stats.__dict__
        import_run.finished_at = timezone.now()
        import_run.save(update_fields=["status", "stats", "finished_at"])
        emit_event(
            event_type="import.completed",
            aggregate_type="import_run",
            aggregate_id=import_run.pk,
            payload=ImportRunSerializer(import_run).data,
            idempotency_key=f"import.completed:{import_run.pk}:{import_run.finished_at.isoformat()}",
        )
    except Exception as exc:
        import_run.status = "failed"
        import_run.error_message = str(exc)
        import_run.finished_at = timezone.now()
        import_run.save(update_fields=["status", "error_message", "finished_at"])
        raise
    finally:
        if upload is not None and path is not None and path.exists():
            path.unlink()

    return import_run
