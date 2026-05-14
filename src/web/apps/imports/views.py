from apps.account.permissions import IsCpprpOrStaff
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import ImportRun
from .serializers import ImportRunSerializer
from .services import run_epp_xlsx_import


@extend_schema_view(
    get=extend_schema(tags=["Imports"], summary="История запусков импорта EPP"),
    post=extend_schema(tags=["Imports"], summary="Запустить импорт EPP из XLSX"),
)
class ImportRunListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ImportRunSerializer
    permission_classes = [IsCpprpOrStaff]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return ImportRun.objects.all()

    def create(self, request, *args, **kwargs):
        upload = request.FILES.get("file")
        import_run = run_epp_xlsx_import(upload=upload, imported_by_id=request.user.id)

        serializer = self.get_serializer(import_run)
        return Response(serializer.data, status=201)
