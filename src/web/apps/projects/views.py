from apps.account.permissions import IsCpprpOrStaff, IsCustomerOrStaff
from apps.outbox.services import emit_event
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, extend_schema_view
from rest_framework import generics, mixins, permissions, serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Project, ProjectStatus
from .pagination import ProjectListPagination
from .serializers import PrimaryProjectSerializer
from .transitions import moderate_project, submit_project_for_moderation


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValidationError({"value": [f"Unsupported boolean value '{value}'."]})


def _base_queryset(user):
    queryset = Project.objects.select_related("owner", "epp").annotate(
        applications_count=Count("applications")
    )
    if user.is_authenticated:
        return queryset.filter(
            Q(status__in=ProjectStatus.catalog_values()) | Q(owner=user)
        ).distinct()
    return queryset.filter(status__in=ProjectStatus.catalog_values())


def _apply_project_filters(queryset, params):
    status = params.get("status")
    q = params.get("q")
    ordering = params.get("ordering")
    source_type = params.get("source_type")
    tech_tag = params.get("tech_tag")
    education_program = params.get("education_program")
    work_format = params.get("work_format")
    staffing_state = params.get("staffing_state")
    application_state = params.get("application_state")
    is_team_project = params.get("is_team_project")
    uses_ai = params.get("uses_ai")
    study_course = params.get("study_course")

    if status:
        if status not in ProjectStatus.values:
            raise ValidationError({"status": [f"Unsupported status '{status}'."]})
        queryset = queryset.filter(status=status)

    if source_type:
        queryset = queryset.filter(source_type=source_type)
    if education_program:
        queryset = queryset.filter(education_program__icontains=education_program.strip())
    if work_format:
        queryset = queryset.filter(work_format__icontains=work_format.strip())
    if study_course:
        if not str(study_course).isdigit():
            raise ValidationError({"study_course": ["study_course must be an integer."]})
        queryset = queryset.filter(study_course=int(study_course))
    if uses_ai is not None:
        parsed_uses_ai = _parse_bool(uses_ai)
        if parsed_uses_ai is not None:
            queryset = queryset.filter(uses_ai=parsed_uses_ai)
    if is_team_project is not None:
        parsed_is_team = _parse_bool(is_team_project)
        if parsed_is_team is not None:
            queryset = (
                queryset.filter(team_size__gt=1) if parsed_is_team else queryset.filter(team_size=1)
            )

    if q:
        queryset = queryset.filter(
            Q(title__icontains=q.strip()) | Q(description__icontains=q.strip())
        )

    items = list(queryset)
    if tech_tag:
        marker = tech_tag.strip().lower()
        items = [item for item in items if marker in {tag.lower() for tag in item.get_tags_list()}]
    if staffing_state:
        items = [item for item in items if item.staffing_state == staffing_state]
    if application_state:
        items = [item for item in items if item.application_window_state == application_state]

    if ordering:
        ordering_field = ordering[1:] if ordering.startswith("-") else ordering
        if ordering_field not in {"created_at", "updated_at"}:
            raise ValidationError(
                {"ordering": ["Unsupported ordering field. Allowed: created_at, updated_at."]}
            )
        reverse = ordering.startswith("-")
        items = sorted(items, key=lambda item: getattr(item, ordering_field), reverse=reverse)
    return items


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=list(ProjectStatus.values),
                description="Filter by project status.",
            ),
            OpenApiParameter(
                name="q",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Case-insensitive search by project title.",
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "Ordering by created_at/updated_at. " "Prefix with '-' for descending order."
                ),
            ),
            OpenApiParameter(
                name="source_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="tech_tag",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="education_program",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="study_course",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="work_format",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="staffing_state",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=["open", "full"],
            ),
            OpenApiParameter(
                name="application_state",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=["open", "closed", "upcoming"],
            ),
            OpenApiParameter(
                name="is_team_project", type=OpenApiTypes.BOOL, location=OpenApiParameter.QUERY
            ),
            OpenApiParameter(
                name="uses_ai",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
            ),
        ]
    )
)
class ProjectListCreateAPIView(generics.ListCreateAPIView):
    queryset = Project.objects.select_related("owner", "epp")
    serializer_class = PrimaryProjectSerializer
    pagination_class = ProjectListPagination
    ordering_fields = ("created_at", "updated_at")

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCustomerOrStaff()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        queryset = _base_queryset(self.request.user)
        return _apply_project_filters(queryset, self.request.query_params)

    def perform_create(self, serializer):
        project = serializer.save(owner=self.request.user, status=ProjectStatus.DRAFT)
        emit_event(
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id=project.pk,
            payload=PrimaryProjectSerializer(project, context={"request": self.request}).data,
            idempotency_key=f"project.changed:{project.pk}:{project.updated_at.isoformat()}:create",
        )


project_list_create_view = ProjectListCreateAPIView.as_view()


class ProjectDetailAPIView(generics.RetrieveAPIView):
    queryset = Project.objects.select_related("owner", "epp").annotate(
        applications_count=Count("applications")
    )
    serializer_class = PrimaryProjectSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return self.queryset.filter(
                Q(status__in=ProjectStatus.catalog_values()) | Q(owner=user)
            ).distinct()
        return self.queryset.filter(status__in=ProjectStatus.catalog_values())


project_detail_view = ProjectDetailAPIView.as_view()


class ProjectUpdateAPIView(generics.UpdateAPIView):
    queryset = Project.objects.select_related("owner", "epp")
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"
    permission_classes = [IsCustomerOrStaff]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(owner=user)


project_update_view = ProjectUpdateAPIView.as_view()


class ProjectDestroyAPIView(generics.DestroyAPIView):
    queryset = Project.objects.select_related("owner", "epp")
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"
    permission_classes = [IsCustomerOrStaff]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(owner=user)


project_destroy_view = ProjectDestroyAPIView.as_view()


class ProjectRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Project.objects.select_related("owner", "epp").annotate(
        applications_count=Count("applications")
    )
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [IsCustomerOrStaff()]

    def get_queryset(self):
        user = self.request.user
        if self.request.method in {"GET", "HEAD", "OPTIONS"}:
            if user.is_authenticated:
                return self.queryset.filter(
                    Q(status__in=ProjectStatus.catalog_values()) | Q(owner=user)
                ).distinct()
            return self.queryset.filter(status__in=ProjectStatus.catalog_values())

        if user.is_staff:
            return self.queryset
        return self.queryset.filter(owner=user)

    def perform_update(self, serializer):
        project = serializer.save()
        emit_event(
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id=project.pk,
            payload=PrimaryProjectSerializer(project, context={"request": self.request}).data,
            idempotency_key=f"project.changed:{project.pk}:{project.updated_at.isoformat()}:update",
        )


project_rud_view = ProjectRetrieveUpdateDestroyAPIView.as_view()


class ProjectModerationInputSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class ProjectSubmitForModerationAPIView(APIView):
    permission_classes = [IsCustomerOrStaff]

    def post(self, request, pk: int):
        project = get_object_or_404(Project.objects.select_related("owner", "epp"), pk=pk)
        submit_project_for_moderation(project=project, actor=request.user)
        emit_event(
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id=project.pk,
            payload=PrimaryProjectSerializer(project, context={"request": request}).data,
            idempotency_key=f"project.changed:{project.pk}:{project.updated_at.isoformat()}:submit",
        )
        serializer = PrimaryProjectSerializer(project, context={"request": request})
        return Response(serializer.data)


class ProjectModerationAPIView(APIView):
    permission_classes = [IsCpprpOrStaff]

    def post(self, request, pk: int):
        payload = ProjectModerationInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        project = get_object_or_404(Project.objects.select_related("owner", "epp"), pk=pk)
        moderate_project(
            project=project,
            actor=request.user,
            decision=payload.validated_data["decision"],
            comment=payload.validated_data["comment"],
        )
        emit_event(
            event_type="project.changed",
            aggregate_type="project",
            aggregate_id=project.pk,
            payload=PrimaryProjectSerializer(project, context={"request": request}).data,
            idempotency_key=f"project.changed:{project.pk}:{project.updated_at.isoformat()}:moderate",
        )
        serializer = PrimaryProjectSerializer(project, context={"request": request})
        return Response(serializer.data)


class CreateAPIView(mixins.CreateModelMixin, generics.GenericAPIView):
    pass


class ProjectMixinView(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    generics.GenericAPIView,
):
    queryset = Project.objects.select_related("owner")
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return self.queryset.filter(
                Q(status__in=ProjectStatus.catalog_values()) | Q(owner=user)
            ).distinct()
        return self.queryset.filter(status__in=ProjectStatus.catalog_values())

    def get(self, request, *args, **kwargs):
        if kwargs.get("pk") is not None:
            return self.retrieve(request, *args, **kwargs)
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


project_mixin_view = ProjectMixinView.as_view()


@api_view(["GET", "POST"])
def project_alt_view(request, pk=None, *args, **kwargs):
    if request.method == "GET":
        if pk is not None:
            obj = get_object_or_404(Project, pk=pk)
            return Response(PrimaryProjectSerializer(obj, many=False).data)

        queryset = Project.objects.filter(status__in=ProjectStatus.catalog_values())
        if request.user.is_authenticated:
            queryset = Project.objects.filter(
                Q(status__in=ProjectStatus.catalog_values()) | Q(owner=request.user)
            ).distinct()
        return Response(PrimaryProjectSerializer(queryset, many=True).data)

    serializer = PrimaryProjectSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(owner=request.user)
    return Response({"data": serializer.data})
