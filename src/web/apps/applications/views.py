import logging

from apps.account.permissions import IsCustomerOrStaff, IsStudentOrStaff
from apps.notifications.services import NotificationSpec, create_notifications
from apps.outbox.services import emit_event
from apps.projects.models import ProjectStatus
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework import serializers as drf_serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Application, ApplicationStatus
from .serializers import ApplicationSerializer
from .transitions import review_application

logger = logging.getLogger(__name__)


@extend_schema_view(
    get=extend_schema(tags=["Applications"], summary="Список заявок"),
    post=extend_schema(tags=["Applications"], summary="Подать заявку на проект"),
)
class ApplicationListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ApplicationSerializer

    def get_permissions(self):
        return [IsStudentOrStaff()]

    def get_queryset(self):
        queryset = Application.objects.select_related("project", "applicant")
        user = self.request.user
        if user.is_staff:
            return queryset
        return queryset.filter(applicant=user)

    def _save_application(self, serializer):
        project = serializer.validated_data["project"]
        if project.status not in ProjectStatus.catalog_values():
            raise ValidationError(
                {"project": ["Applications are allowed only for projects visible in catalog."]}
            )
        if project.application_window_state != "open":
            raise ValidationError(
                {
                    "project": [
                        (
                            "Applications are allowed only while the project "
                            "application window is open."
                        )
                    ]
                }
            )
        return serializer.save(
            applicant=self.request.user,
            status=ApplicationStatus.SUBMITTED,
        )

    def _run_post_create_side_effects(self, application):
        create_notifications(
            recipients=[application.applicant],
            spec=NotificationSpec(
                event_type="application.created",
                title="Заявка отправлена",
                body="Ваша заявка на участие в проекте отправлена.",
                target_type="application",
                target_id=str(application.pk),
                actor_id=getattr(self.request.user, "id", None),
                dedupe_key=f"application.created:\
                    {application.pk}:\
                        {application.created_at.isoformat() if application.created_at else ''}",
            ),
        )
        create_notifications(
            recipients=[getattr(application.project, "owner", None)],
            spec=NotificationSpec(
                event_type="application.received",
                title="Новая заявка на проект",
                body="Поступила новая заявка на ваш проект.",
                target_type="application",
                target_id=str(application.pk),
                actor_id=getattr(self.request.user, "id", None),
                dedupe_key=f"application.received:\
                    {application.pk}:\
                        {application.created_at.isoformat() if application.created_at else ''}",
            ),
        )
        emit_event(
            event_type="application.changed",
            aggregate_type="application",
            aggregate_id=application.pk,
            payload=ApplicationSerializer(application, context={"request": self.request}).data,
            idempotency_key=f"application.changed:{application.pk}:{application.updated_at.isoformat()}:create",
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = self._save_application(serializer)
        response_serializer = self.get_serializer(application)
        headers = self.get_success_headers(response_serializer.data)

        try:
            self._run_post_create_side_effects(application)
        except Exception:
            logger.exception(
                "Application post-create side effects failed",
                extra={"application_id": application.pk, "applicant_id": application.applicant_id},
            )

        return Response(response_serializer.data, status=201, headers=headers)


@extend_schema_view(
    get=extend_schema(tags=["Applications"], summary="Получить заявку"),
    patch=extend_schema(tags=["Applications"], summary="Обновить заявку частично"),
    put=extend_schema(tags=["Applications"], summary="Полностью обновить заявку"),
    delete=extend_schema(tags=["Applications"], summary="Удалить заявку"),
)
class ApplicationRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [IsStudentOrStaff]
    lookup_field = "pk"

    def get_queryset(self):
        queryset = Application.objects.select_related("project", "applicant")
        user = self.request.user
        if user.is_staff:
            return queryset
        return queryset.filter(applicant=user)

    def perform_destroy(self, instance):
        aggregate_id = instance.pk
        applicant = getattr(instance, "applicant", None)
        project_owner = getattr(getattr(instance, "project", None), "owner", None)
        updated_at = getattr(instance, "updated_at", None)
        payload = {
            "id": aggregate_id,
            "project": instance.project_id,
            "applicant": instance.applicant_id,
            "status": "deleted",
            "tombstone": True,
            "created_at": instance.created_at.isoformat() if instance.created_at else None,
            "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
            "deleted_at": timezone.now().isoformat(),
        }
        super().perform_destroy(instance)
        create_notifications(
            recipients=[applicant],
            spec=NotificationSpec(
                event_type="application.deleted",
                title="Заявка удалена",
                body="Ваша заявка была удалена (отозвана).",
                target_type="application",
                target_id=str(aggregate_id),
                actor_id=getattr(self.request.user, "id", None),
                dedupe_key=f"application.deleted:\
                    {aggregate_id}:\
                        {updated_at.isoformat() if updated_at else payload['deleted_at']}",
            ),
        )
        create_notifications(
            recipients=[project_owner],
            spec=NotificationSpec(
                event_type="application.withdrawn",
                title="Заявка отозвана",
                body="Заявка студента была отозвана.",
                target_type="application",
                target_id=str(aggregate_id),
                actor_id=getattr(self.request.user, "id", None),
                dedupe_key=f"application.withdrawn:\
                    {aggregate_id}:\
                        {updated_at.isoformat() if updated_at else payload['deleted_at']}",
            ),
        )
        emit_event(
            event_type="application.deleted",
            aggregate_type="application",
            aggregate_id=aggregate_id,
            payload=payload,
            idempotency_key=f"application.deleted:{aggregate_id}:{payload['deleted_at']}",
        )


class ApplicationReviewInputSerializer(drf_serializers.Serializer):
    decision = drf_serializers.ChoiceField(choices=["accept", "reject"])
    comment = drf_serializers.CharField(required=False, allow_blank=True, default="")


class ApplicationReviewAPIView(APIView):
    permission_classes = [IsCustomerOrStaff]

    @extend_schema(
        tags=["Applications"],
        summary="Рассмотреть заявку",
        request=ApplicationReviewInputSerializer,
        responses=ApplicationSerializer,
    )
    def post(self, request, pk: int):
        payload = ApplicationReviewInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        application = generics.get_object_or_404(
            Application.objects.select_related("project", "project__owner", "applicant"),
            pk=pk,
        )
        review_application(
            application=application,
            actor=request.user,
            decision=payload.validated_data["decision"],
            comment=payload.validated_data["comment"],
        )
        decision = payload.validated_data["decision"]
        if decision == "accept":
            title = "Заявка принята"
            event_type = "application.review.accepted"
            body = "Ваша заявка принята."
        else:
            title = "Заявка отклонена"
            event_type = "application.review.rejected"
            body = "Ваша заявка отклонена."
        comment_text = (payload.validated_data.get("comment") or "").strip()
        if comment_text:
            body = f"{body}\n\nКомментарий: {comment_text}"
        create_notifications(
            recipients=[application.applicant],
            spec=NotificationSpec(
                event_type=event_type,
                title=title,
                body=body,
                target_type="application",
                target_id=str(application.pk),
                actor_id=getattr(request.user, "id", None),
                dedupe_key=f"{event_type}:\
                    {application.pk}:\
                        {application.reviewed_at.isoformat() if application.reviewed_at else ''}",
            ),
        )
        create_notifications(
            recipients=[getattr(application.project, "owner", None)],
            spec=NotificationSpec(
                event_type="application.reviewed",
                title="Заявка рассмотрена",
                body="Вы приняли решение по заявке на проект.",
                target_type="application",
                target_id=str(application.pk),
                actor_id=getattr(request.user, "id", None),
                dedupe_key=f"application.reviewed:\
                    {application.pk}:\
                        {application.reviewed_at.isoformat() if application.reviewed_at else ''}",
            ),
        )
        emit_event(
            event_type="application.changed",
            aggregate_type="application",
            aggregate_id=application.pk,
            payload=ApplicationSerializer(application, context={"request": request}).data,
            idempotency_key=f"application.changed:{application.pk}:{application.updated_at.isoformat()}:review",
        )
        serializer = ApplicationSerializer(application, context={"request": request})
        return Response(serializer.data)
