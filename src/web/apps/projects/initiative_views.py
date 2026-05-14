from apps.account.permissions import IsCpprpOrStaff, IsStudentOrStaff
from apps.notifications.services import NotificationSpec, create_notifications
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
        tags=["Projects"],
        summary="Список инициативных предложений",
        parameters=[
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=list(InitiativeProposalStatus.values),
                description="Filter by initiative proposal status.",
            )
        ]
    ),
    post=extend_schema(tags=["Projects"], summary="Создать инициативное предложение"),
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
        proposal = serializer.save(owner=self.request.user, status=InitiativeProposalStatus.DRAFT)
        create_notifications(
            recipients=[proposal.owner],
            spec=NotificationSpec(
                event_type="initiative.created",
                title="Инициатива создана",
                body="Инициатива создана в статусе «черновик». \
                    Вы можете отправить её на модерацию.",
                target_type="initiative",
                target_id=str(proposal.pk),
                actor_id=getattr(self.request.user, "id", None),
                dedupe_key=f"initiative.created:\
                    {proposal.pk}:\
                        {proposal.created_at.isoformat() if proposal.created_at else ''}",
            ),
        )


initiative_proposal_list_create_view = InitiativeProposalListCreateAPIView.as_view()


@extend_schema_view(
    get=extend_schema(tags=["Projects"], summary="Детали инициативного предложения"),
    patch=extend_schema(tags=["Projects"], summary="Обновить инициативу частично"),
    put=extend_schema(tags=["Projects"], summary="Полностью обновить инициативу"),
    delete=extend_schema(tags=["Projects"], summary="Удалить инициативу"),
)
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
        proposal = serializer.save()
        create_notifications(
            recipients=[proposal.owner],
            spec=NotificationSpec(
                event_type="initiative.updated",
                title="Инициатива обновлена",
                body="Данные инициативы были обновлены.",
                target_type="initiative",
                target_id=str(proposal.pk),
                actor_id=getattr(self.request.user, "id", None),
                dedupe_key=f"initiative.updated:\
                    {proposal.pk}:\
                        {proposal.updated_at.isoformat() if proposal.updated_at else ''}",
            ),
        )

    def perform_destroy(self, instance):
        _ensure_initiative_proposal_editable(instance)
        owner = getattr(instance, "owner", None)
        proposal_id = getattr(instance, "pk", None)
        updated_at = getattr(instance, "updated_at", None)
        super().perform_destroy(instance)
        create_notifications(
            recipients=[owner],
            spec=NotificationSpec(
                event_type="initiative.deleted",
                title="Инициатива удалена",
                body="Инициатива была удалена.",
                target_type="initiative",
                target_id=str(proposal_id),
                actor_id=getattr(self.request.user, "id", None),
                dedupe_key=f"initiative.deleted:\
                    {proposal_id}:\
                        {updated_at.isoformat() if updated_at else ''}",
            ),
        )


initiative_proposal_rud_view = InitiativeProposalRetrieveUpdateDestroyAPIView.as_view()


class InitiativeProposalSubmitForModerationAPIView(APIView):
    permission_classes = [IsStudentOrStaff]

    @extend_schema(
        tags=["Projects"],
        summary="Отправить инициативу на модерацию",
        request=None,
        responses=InitiativeProposalSerializer,
    )
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
        tags=["Projects"],
        summary="Рассмотреть инициативное предложение",
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

        serializer = InitiativeProposalSerializer(proposal, context={"request": request})
        return Response(serializer.data)
