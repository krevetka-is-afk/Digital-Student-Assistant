from apps.account.permissions import IsCpprpOrStaff, IsStudentOrStaff
from apps.outbox.services import emit_event
from apps.users.models import UserRole
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, extend_schema_view
from rest_framework import generics, permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .initiative_models import InitiativeProposal, InitiativeProposalStatus
from .initiative_serializers import InitiativeProposalSerializer
from .initiative_transitions import (
    moderate_initiative_proposal,
    submit_initiative_proposal_for_moderation,
)
from .pagination import ProjectListPagination
from .serializers import PrimaryProjectSerializer


def _base_initiative_queryset(user):
    queryset = InitiativeProposal.objects.select_related(
        "owner", "moderated_by", "published_project"
    ).prefetch_related("submissions__submitted_by", "submissions__reviewed_by")
    if user.is_staff:
        return queryset
    if (
        getattr(user, "is_authenticated", False)
        and getattr(getattr(user, "profile", None), "role", None) == UserRole.CPPRP
    ):
        return queryset
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset.filter(owner=user)


def _apply_initiative_filters(queryset, params):
    status = params.get("status")
    if status:
        if status not in InitiativeProposalStatus.values:
            raise serializers.ValidationError({"status": [f"Unsupported status '{status}'."]})
        queryset = queryset.filter(status=status)
    return queryset.order_by("-updated_at", "-created_at")


def _ensure_initiative_proposal_editable(proposal: InitiativeProposal):
    if proposal.status not in {
        InitiativeProposalStatus.DRAFT,
        InitiativeProposalStatus.REVISION_REQUESTED,
    }:
        raise serializers.ValidationError(
            {
                "status": [
                    "Initiative proposal can be edited only in draft or revision requested status."
                ]
            }
        )


class InitiativeProposalModerationInputSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(required=False, allow_blank=True, default="")


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=list(InitiativeProposalStatus.values),
                description="Filter by initiative proposal status.",
            )
        ]
    )
)
class InitiativeProposalListCreateAPIView(generics.ListCreateAPIView):
    queryset = InitiativeProposal.objects.select_related(
        "owner", "moderated_by", "published_project"
    ).prefetch_related("submissions__submitted_by", "submissions__reviewed_by")
    serializer_class = InitiativeProposalSerializer
    pagination_class = ProjectListPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsStudentOrStaff()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = _base_initiative_queryset(self.request.user)
        return _apply_initiative_filters(queryset, self.request.query_params)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, status=InitiativeProposalStatus.DRAFT)


initiative_proposal_list_create_view = InitiativeProposalListCreateAPIView.as_view()


class InitiativeProposalRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = InitiativeProposal.objects.select_related(
        "owner", "moderated_by", "published_project"
    ).prefetch_related("submissions__submitted_by", "submissions__reviewed_by")
    serializer_class = InitiativeProposalSerializer
    lookup_field = "pk"

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [IsStudentOrStaff()]

    def get_queryset(self):
        if self.request.method in {"GET", "HEAD", "OPTIONS"}:
            return _base_initiative_queryset(self.request.user)
        user = self.request.user
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(owner=user)

    def perform_update(self, serializer):
        _ensure_initiative_proposal_editable(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        _ensure_initiative_proposal_editable(instance)
        super().perform_destroy(instance)


initiative_proposal_rud_view = InitiativeProposalRetrieveUpdateDestroyAPIView.as_view()


class InitiativeProposalSubmitForModerationAPIView(APIView):
    permission_classes = [IsStudentOrStaff]

    @extend_schema(request=None, responses=InitiativeProposalSerializer)
    def post(self, request, pk: int):
        proposal = get_object_or_404(
            InitiativeProposal.objects.select_related("owner", "moderated_by", "published_project"),
            pk=pk,
        )
        proposal = submit_initiative_proposal_for_moderation(proposal=proposal, actor=request.user)
        serializer = InitiativeProposalSerializer(proposal, context={"request": request})
        return Response(serializer.data)


class InitiativeProposalModerationAPIView(APIView):
    permission_classes = [IsCpprpOrStaff]

    @extend_schema(
        request=InitiativeProposalModerationInputSerializer,
        responses=InitiativeProposalSerializer,
    )
    def post(self, request, pk: int):
        payload = InitiativeProposalModerationInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        proposal = get_object_or_404(
            InitiativeProposal.objects.select_related(
                "owner", "moderated_by", "published_project"
            ).prefetch_related("submissions"),
            pk=pk,
        )
        proposal = moderate_initiative_proposal(
            proposal=proposal,
            actor=request.user,
            decision=payload.validated_data["decision"],
            comment=payload.validated_data["comment"],
        )

        if proposal.published_project_id is not None and proposal.published_project is not None:
            project = proposal.published_project
            project_pk = project.pk
            project_updated_at = project.updated_at
            if project_pk is None or project_updated_at is None:
                serializer = InitiativeProposalSerializer(proposal, context={"request": request})
                return Response(serializer.data)
            emit_event(
                event_type="project.changed",
                aggregate_type="project",
                aggregate_id=project_pk,
                payload=PrimaryProjectSerializer(project, context={"request": request}).data,
                idempotency_key=(
                    f"project.changed:{project_pk}:{project_updated_at.isoformat()}:initiative-publish"
                ),
            )

        serializer = InitiativeProposalSerializer(proposal, context={"request": request})
        return Response(serializer.data)
