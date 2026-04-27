from apps.account.permissions import IsOutboxConsumerOrCpprpOrStaff
from apps.applications.models import Application
from apps.faculty.models import (
    FacultyCourse,
    FacultyPerson,
    FacultyPublication,
    ProjectFacultyMatch,
)
from apps.projects.models import Project, ProjectStatus
from apps.users.models import UserProfile
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OutboxEvent
from .serializers import (
    OutboxAckResponseSerializer,
    OutboxAckSerializer,
    OutboxConsumerCheckpointSerializer,
    OutboxEventSerializer,
    OutboxSnapshotResponseSerializer,
)
from .services import (
    ack_event,
    build_delivery_queryset,
    get_or_create_consumer_checkpoint,
    mark_polled,
    normalize_consumer_name,
)


class OutboxEventListAPIView(generics.ListAPIView):
    serializer_class = OutboxEventSerializer
    permission_classes = [IsOutboxConsumerOrCpprpOrStaff]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="event_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by event type.",
            ),
            OpenApiParameter(
                name="since_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Legacy lower bound (exclusive) by event id.",
            ),
            OpenApiParameter(
                name="consumer",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Consumer name for checkpoint-aware incremental polling.",
            ),
            OpenApiParameter(
                name="mode",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=["poll", "replay"],
                description="poll starts from consumer checkpoint; \
                replay reads from replay_from_id.",
            ),
            OpenApiParameter(
                name="replay_from_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Inclusive lower bound for replay mode.",
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        if value is None or not value.isdigit():
            return None
        return int(value)

    def get_queryset(self):
        queryset = OutboxEvent.objects.all()
        event_type = self.request.query_params.get("event_type")
        since_id = self._parse_int(self.request.query_params.get("since_id"))
        consumer_raw = self.request.query_params.get("consumer")
        try:
            consumer = normalize_consumer_name(consumer_raw) if consumer_raw is not None else ""
        except ValueError:
            raise ValidationError({"consumer": ["consumer must not be blank."]}) from None
        mode = (self.request.query_params.get("mode") or "poll").strip()
        replay_from_id = self._parse_int(self.request.query_params.get("replay_from_id"))

        self._delivery_checkpoint = None
        self._delivery_mode = mode

        if event_type:
            queryset = queryset.filter(event_type=event_type)

        if mode not in {"poll", "replay"}:
            raise ValidationError({"mode": ["Unsupported mode. Allowed: poll, replay."]})

        if (mode == "replay" or replay_from_id is not None) and not consumer:
            raise ValidationError({"consumer": ["consumer is required for replay mode."]})

        if consumer:
            checkpoint = get_or_create_consumer_checkpoint(consumer)
            self._delivery_checkpoint = checkpoint
            return build_delivery_queryset(
                checkpoint=checkpoint,
                event_type=event_type,
                since_id=since_id,
                mode=mode,
                replay_from_id=replay_from_id,
            )

        if since_id is not None:
            queryset = queryset.filter(id__gt=since_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        checkpoint = getattr(self, "_delivery_checkpoint", None)
        if checkpoint is not None:
            context["checkpoint_id"] = checkpoint.last_acked_event_id
        return context

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        checkpoint = getattr(self, "_delivery_checkpoint", None)
        if checkpoint is None:
            return response

        results = response.data.get("results", [])
        max_event_id = max((int(item["id"]) for item in results), default=None)
        mark_polled(checkpoint=checkpoint, max_event_id=max_event_id)
        checkpoint.refresh_from_db()
        response.data["delivery"] = {
            "consumer": checkpoint.consumer,
            "mode": self._delivery_mode,
            "status": checkpoint.status,
            "checkpoint": checkpoint.last_acked_event_id,
            "last_seen_event_id": checkpoint.last_seen_event_id,
        }
        return response


class OutboxEventAckAPIView(APIView):
    permission_classes = [IsOutboxConsumerOrCpprpOrStaff]

    @extend_schema(request=OutboxAckSerializer, responses=OutboxAckResponseSerializer)
    def post(self, request):
        serializer = OutboxAckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            checkpoint, ack_status = ack_event(
                consumer=serializer.validated_data["consumer"],
                event_id=serializer.validated_data["event_id"],
            )
        except OutboxEvent.DoesNotExist:
            raise ValidationError(
                {"event_id": ["Referenced outbox event does not exist."]}
            ) from None

        payload = {"ack_status": ack_status, **OutboxConsumerCheckpointSerializer(checkpoint).data}
        return Response(payload)


class OutboxConsumerCheckpointAPIView(APIView):
    permission_classes = [IsOutboxConsumerOrCpprpOrStaff]

    @extend_schema(responses=OutboxConsumerCheckpointSerializer)
    def get(self, request, consumer: str):
        checkpoint = get_or_create_consumer_checkpoint(consumer)
        serializer = OutboxConsumerCheckpointSerializer(checkpoint)
        return Response(serializer.data)


class OutboxSnapshotAPIView(APIView):
    permission_classes = [IsOutboxConsumerOrCpprpOrStaff]
    allowed_resources = {
        "projects",
        "applications",
        "user_profiles",
        "faculty_persons",
        "faculty_publications",
        "faculty_courses",
        "project_faculty_matches",
    }

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="resources",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "Optional comma-separated snapshot resources. "
                    "Allowed: projects, applications, user_profiles, faculty_persons, "
                    "faculty_publications, faculty_courses, project_faculty_matches. "
                    "Default: core resources."
                ),
            )
        ],
        responses=OutboxSnapshotResponseSerializer,
    )
    def get(self, request):
        resources_param = (request.query_params.get("resources") or "").strip()
        if resources_param:
            resources = [item.strip() for item in resources_param.split(",") if item.strip()]
        else:
            resources = ["projects", "applications", "user_profiles"]

        invalid = sorted(set(resources) - self.allowed_resources)
        if invalid:
            raise ValidationError(
                {
                    "resources": [
                        "Unsupported resources: " + ", ".join(invalid) + ". "
                        "Allowed: " + ", ".join(sorted(self.allowed_resources)) + "."
                    ]
                }
            )

        watermark = OutboxEvent.objects.order_by("-id").values_list("id", flat=True).first() or 0
        payload = {
            "watermark": watermark,
            "generated_at": timezone.now(),
            "resources": resources,
        }

        if "projects" in resources:
            payload["projects"] = Project.objects.filter(
                status__in=ProjectStatus.catalog_values()
            ).select_related("owner", "epp")
        if "applications" in resources:
            payload["applications"] = Application.objects.select_related(
                "project", "project__owner", "project__epp", "applicant", "reviewed_by"
            )
        if "user_profiles" in resources:
            payload["user_profiles"] = UserProfile.objects.select_related("user")
        if "faculty_persons" in resources:
            payload["faculty_persons"] = FacultyPerson.objects.filter(is_stale=False)
        if "faculty_publications" in resources:
            payload["faculty_publications"] = FacultyPublication.objects.prefetch_related(
                "authorships__person"
            )
        if "faculty_courses" in resources:
            payload["faculty_courses"] = FacultyCourse.objects.select_related("person")
        if "project_faculty_matches" in resources:
            payload["project_faculty_matches"] = ProjectFacultyMatch.objects.select_related(
                "project",
                "faculty_person",
            )

        serializer = OutboxSnapshotResponseSerializer(payload, context={"request": request})
        return Response(serializer.data)
