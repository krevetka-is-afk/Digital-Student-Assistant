from pathlib import Path
from tempfile import NamedTemporaryFile

from apps.account.permissions import IsCpprpOrStaff
from apps.outbox.services import emit_event
from apps.projects.importers import default_epp_xlsx_path, import_epp_xlsx
from django.utils import timezone
from rest_framework import generics
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import ImportRun
from .serializers import ImportRunSerializer


class ImportRunListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ImportRunSerializer
    permission_classes = [IsCpprpOrStaff]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return ImportRun.objects.all()

    def create(self, request, *args, **kwargs):
        upload = request.FILES.get("file")
        import_run = ImportRun.objects.create(
            source="xlsx",
            source_name=getattr(upload, "name", default_epp_xlsx_path().name),
            imported_by_id=request.user.id,
            status="running",
        )
        path: Path | None = None
        try:
            if upload is not None:
                raw_suffix = Path(getattr(upload, "name", "")).suffix.lower()
                allowed_suffixes = {".xlsx", ".xlsm"}
                suffix = raw_suffix if raw_suffix in allowed_suffixes else ".xlsx"
                with NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
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

        serializer = self.get_serializer(import_run)
        return Response(serializer.data, status=201)
