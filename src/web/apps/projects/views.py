from django.db.models import Q
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
        ]
    )
)
class ProjectListCreateAPIView(generics.ListCreateAPIView):
    queryset = Project.objects.select_related("owner")
    serializer_class = PrimaryProjectSerializer
    pagination_class = ProjectListPagination
    ordering_fields = ("created_at", "updated_at")

    def get_queryset(self):
        user = self.request.user
        status = self.request.query_params.get("status")
        q = self.request.query_params.get("q")
        ordering = self.request.query_params.get("ordering")

        if user.is_authenticated:
            queryset = self.queryset.filter(
                Q(status__in=ProjectStatus.catalog_values()) | Q(owner=user)
            ).distinct()
        else:
            queryset = self.queryset.filter(status__in=ProjectStatus.catalog_values())

        if status:
            if status not in ProjectStatus.values:
                raise ValidationError({"status": [f"Unsupported status '{status}'."]})
            queryset = queryset.filter(status=status)

        if q:
            queryset = queryset.filter(title__icontains=q.strip())

        if ordering:
            ordering_field = ordering[1:] if ordering.startswith("-") else ordering
            if ordering_field not in self.ordering_fields:
                raise ValidationError(
                    {"ordering": ["Unsupported ordering field. Allowed: created_at, updated_at."]}
                )
            queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, status=ProjectStatus.DRAFT)


project_list_create_view = ProjectListCreateAPIView.as_view()


class ProjectDetailAPIView(generics.RetrieveAPIView):
    queryset = Project.objects.select_related("owner")
    serializer_class = PrimaryProjectSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return self.queryset.filter(
                Q(status__in=ProjectStatus.catalog_values()) | Q(owner=user)
            ).distinct()
        return self.queryset.filter(status__in=ProjectStatus.catalog_values())


project_detail_view = ProjectDetailAPIView.as_view()


class ProjectUpdateAPIView(generics.UpdateAPIView):
    queryset = Project.objects.select_related("owner")
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(owner=user)


project_update_view = ProjectUpdateAPIView.as_view()


class ProjectDestroyAPIView(generics.DestroyAPIView):
    queryset = Project.objects.select_related("owner")
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(owner=user)


project_destroy_view = ProjectDestroyAPIView.as_view()


class ProjectRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Project.objects.select_related("owner")
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"

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


project_rud_view = ProjectRetrieveUpdateDestroyAPIView.as_view()


class ProjectModerationInputSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class ProjectSubmitForModerationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)
        submit_project_for_moderation(project=project, actor=request.user)
        serializer = PrimaryProjectSerializer(project, context={"request": request})
        return Response(serializer.data)


class ProjectModerationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        payload = ProjectModerationInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)
        moderate_project(
            project=project,
            actor=request.user,
            decision=payload.validated_data["decision"],
            comment=payload.validated_data["comment"],
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
