from apps.outbox.services import emit_event
from apps.projects.models import ProjectStatus
from rest_framework import generics, permissions
from rest_framework import serializers as drf_serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Application, ApplicationStatus
from .serializers import ApplicationSerializer
from .transitions import review_application


class ApplicationListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Application.objects.select_related("project", "applicant")
        user = self.request.user
        if user.is_staff:
            return queryset
        return queryset.filter(applicant=user)

    def perform_create(self, serializer):
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
        application = serializer.save(
            applicant=self.request.user,
            status=ApplicationStatus.SUBMITTED,
        )
        emit_event(
            event_type="application.changed",
            aggregate_type="application",
            aggregate_id=application.pk,
            payload=ApplicationSerializer(application, context={"request": self.request}).data,
            idempotency_key=f"application.changed:{application.pk}:{application.updated_at.isoformat()}:create",
        )


class ApplicationRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        queryset = Application.objects.select_related("project", "applicant")
        user = self.request.user
        if user.is_staff:
            return queryset
        return queryset.filter(applicant=user)


class ApplicationReviewInputSerializer(drf_serializers.Serializer):
    decision = drf_serializers.ChoiceField(choices=["accept", "reject"])
    comment = drf_serializers.CharField(required=False, allow_blank=True, default="")


class ApplicationReviewAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

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
        emit_event(
            event_type="application.changed",
            aggregate_type="application",
            aggregate_id=application.pk,
            payload=ApplicationSerializer(application, context={"request": request}).data,
            idempotency_key=f"application.changed:{application.pk}:{application.updated_at.isoformat()}:review",
        )
        serializer = ApplicationSerializer(application, context={"request": request})
        return Response(serializer.data)
