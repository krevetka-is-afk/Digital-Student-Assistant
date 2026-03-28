import csv

from apps.applications.models import Application, ApplicationStatus
from apps.outbox.services import emit_event
from apps.projects.models import Project, ProjectStatus
from apps.projects.pagination import ProjectListPagination
from apps.users.models import UserProfile
from django.db.models import Count, Q
from django.http import HttpResponse
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DeadlineAudience, DocumentTemplate, PlatformDeadline
from .permissions import IsCpprpOrStaff, IsCustomerOrStaff, IsStudentOrStaff, get_user_role
from .serializers import (
    AccountApplicationSerializer,
    AccountOverviewSerializer,
    AccountProjectSerializer,
    CPPRPApplicationsOverviewSerializer,
    DocumentTemplateSerializer,
    PlatformDeadlineSerializer,
    StudentOverviewSerializer,
)


class CPPRPApplicationsPagination(ProjectListPagination):
    page_size = 20


def _get_profile(user) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _active_deadlines_for(role: str) -> list[PlatformDeadline]:
    return list(
        PlatformDeadline.objects.filter(
            is_active=True,
            audience__in=[DeadlineAudience.GLOBAL, role],
        )
    )


def _active_templates_for(role: str) -> list[DocumentTemplate]:
    return list(
        DocumentTemplate.objects.filter(
            is_active=True,
            audience__in=[DeadlineAudience.GLOBAL, role],
        )
    )


def _build_counters(user, profile: UserProfile) -> dict[str, int]:
    applications_qs = Application.objects.filter(applicant=user)
    projects_qs = Project.objects.filter(owner=user)
    if user.is_staff or profile.role == "cpprp":
        projects_on_moderation = Project.objects.filter(status=ProjectStatus.ON_MODERATION).count()
        incoming_submitted = Application.objects.filter(status=ApplicationStatus.SUBMITTED).count()
    else:
        projects_on_moderation = projects_qs.filter(status=ProjectStatus.ON_MODERATION).count()
        incoming_submitted = Application.objects.filter(
            project__owner=user,
            status=ApplicationStatus.SUBMITTED,
        ).count()
    return {
        "applications_total": applications_qs.count(),
        "projects_total": projects_qs.count(),
        "projects_on_moderation": projects_on_moderation,
        "incoming_submitted_applications": incoming_submitted,
        "favorite_projects_total": len(profile.favorite_project_ids or []),
    }


class AccountMeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = _get_profile(request.user)
        payload = {
            "profile": profile,
            "counters": _build_counters(request.user, profile),
        }
        return Response(AccountOverviewSerializer(payload).data)


class StudentOverviewAPIView(APIView):
    permission_classes = [IsStudentOrStaff]

    def get(self, request):
        role = get_user_role(request.user) or "student"
        profile = _get_profile(request.user)
        applications = (
            Application.objects.select_related("project", "project__epp", "applicant")
            .filter(applicant=request.user)
            .order_by("-created_at")
        )
        favorites = list(
            Project.objects.filter(pk__in=profile.favorite_project_ids or [])
            .select_related("owner", "epp")
            .order_by("-updated_at")
        )
        payload = {
            "profile": profile,
            "counters": _build_counters(request.user, profile),
            "applications": applications,
            "favorite_projects": favorites,
            "deadlines": _active_deadlines_for(role),
            "templates": _active_templates_for(role),
        }
        return Response(StudentOverviewSerializer(payload, context={"request": request}).data)


class CustomerProjectsAPIView(generics.ListAPIView):
    permission_classes = [IsCustomerOrStaff]
    serializer_class = AccountProjectSerializer
    pagination_class = ProjectListPagination

    def get_queryset(self):
        return (
            Project.objects.select_related("epp")
            .filter(owner=self.request.user)
            .annotate(
                submitted_applications_count=Count(
                    "applications",
                    filter=Q(applications__status=ApplicationStatus.SUBMITTED),
                )
            )
            .order_by("-updated_at")
        )


class CustomerApplicationsAPIView(generics.ListAPIView):
    permission_classes = [IsCustomerOrStaff]
    serializer_class = AccountApplicationSerializer
    pagination_class = ProjectListPagination

    def get_queryset(self):
        return (
            Application.objects.select_related("project", "project__epp", "applicant")
            .filter(project__owner=self.request.user)
            .order_by("-created_at")
        )


class CPPRPModerationQueueAPIView(generics.ListAPIView):
    permission_classes = [IsCpprpOrStaff]
    serializer_class = AccountProjectSerializer
    pagination_class = ProjectListPagination

    def get_queryset(self):
        return (
            Project.objects.select_related("epp", "owner")
            .filter(status=ProjectStatus.ON_MODERATION)
            .annotate(
                submitted_applications_count=Count(
                    "applications",
                    filter=Q(applications__status=ApplicationStatus.SUBMITTED),
                )
            )
            .order_by("-updated_at")
        )


class CPPRPApplicationsAPIView(APIView):
    permission_classes = [IsCpprpOrStaff]
    pagination_class = CPPRPApplicationsPagination

    def get(self, request):
        queryset = Application.objects.select_related("project", "project__epp", "applicant")
        totals = {
            ApplicationStatus.SUBMITTED: queryset.filter(
                status=ApplicationStatus.SUBMITTED
            ).count(),
            ApplicationStatus.ACCEPTED: queryset.filter(status=ApplicationStatus.ACCEPTED).count(),
            ApplicationStatus.REJECTED: queryset.filter(status=ApplicationStatus.REJECTED).count(),
        }
        recent_queryset = queryset.order_by("-created_at")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(recent_queryset, request, view=self)
        recent = paginator.get_paginated_response(
            AccountApplicationSerializer(page, many=True).data
        ).data
        payload = {"totals": totals, "recent": recent}
        return Response(CPPRPApplicationsOverviewSerializer(payload).data)


class PlatformDeadlineListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = PlatformDeadlineSerializer
    permission_classes = [IsCpprpOrStaff]

    def get_queryset(self):
        return PlatformDeadline.objects.all()

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        emit_event(
            event_type="deadline.changed",
            aggregate_type="deadline",
            aggregate_id=response.data["id"],
            payload=response.data,
            idempotency_key=f"deadline.changed:{response.data['id']}:create",
        )
        return response


class DocumentTemplateListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = DocumentTemplateSerializer
    permission_classes = [IsCpprpOrStaff]

    def get_queryset(self):
        return DocumentTemplate.objects.all()


class CPPRPProjectsExportAPIView(APIView):
    permission_classes = [IsCpprpOrStaff]

    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="projects-export.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "project_id",
                "title",
                "status",
                "source_type",
                "team_size",
                "accepted_participants_count",
                "education_program",
                "study_course",
            ]
        )
        for project in Project.objects.order_by("pk"):
            writer.writerow(
                [
                    project.pk,
                    project.title,
                    project.status,
                    project.source_type,
                    project.team_size,
                    project.accepted_participants_count,
                    project.education_program,
                    project.study_course,
                ]
            )
        return response


class CPPRPApplicationsExportAPIView(APIView):
    permission_classes = [IsCpprpOrStaff]

    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="applications-export.csv"'
        writer = csv.writer(response)
        writer.writerow(["application_id", "project_id", "applicant_id", "status", "created_at"])
        for application in Application.objects.order_by("pk"):
            writer.writerow(
                [
                    application.pk,
                    application.project_id,
                    application.applicant_id,
                    application.status,
                    application.created_at.isoformat(),
                ]
            )
        return response
