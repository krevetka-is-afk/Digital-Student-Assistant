from apps.applications.models import Application, ApplicationStatus
from apps.projects.models import Project, ProjectStatus
from apps.users.models import UserProfile
from django.db.models import Count, Q
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import require_roles
from .serializers import (
    AccountApplicationSerializer,
    AccountOverviewSerializer,
    AccountProjectSerializer,
    CPPRPApplicationsOverviewSerializer,
    StudentOverviewSerializer,
)


def _get_profile(user) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


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
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request.user, allowed={"student"})
        profile = _get_profile(request.user)
        applications = (
            Application.objects.select_related("project", "project__epp", "applicant")
            .filter(applicant=request.user)
            .order_by("-created_at")
        )
        payload = {
            "profile": profile,
            "counters": _build_counters(request.user, profile),
            "applications": applications,
        }
        return Response(StudentOverviewSerializer(payload).data)


class CustomerProjectsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request.user, allowed={"customer"})
        queryset = (
            Project.objects.select_related("epp")
            .filter(owner=request.user)
            .annotate(
                submitted_applications_count=Count(
                    "applications",
                    filter=Q(applications__status=ApplicationStatus.SUBMITTED),
                )
            )
            .order_by("-updated_at")
        )
        return Response(AccountProjectSerializer(queryset, many=True).data)


class CustomerApplicationsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request.user, allowed={"customer"})
        queryset = (
            Application.objects.select_related("project", "project__epp", "applicant")
            .filter(project__owner=request.user)
            .order_by("-created_at")
        )
        return Response(AccountApplicationSerializer(queryset, many=True).data)


class CPPRPModerationQueueAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request.user, allowed={"cpprp"})
        queryset = (
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
        return Response(AccountProjectSerializer(queryset, many=True).data)


class CPPRPApplicationsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request.user, allowed={"cpprp"})
        queryset = Application.objects.select_related("project", "project__epp", "applicant")
        totals = {
            ApplicationStatus.SUBMITTED: queryset.filter(
                status=ApplicationStatus.SUBMITTED
            ).count(),
            ApplicationStatus.ACCEPTED: queryset.filter(status=ApplicationStatus.ACCEPTED).count(),
            ApplicationStatus.REJECTED: queryset.filter(status=ApplicationStatus.REJECTED).count(),
        }
        recent = queryset.order_by("-created_at")[:20]
        payload = {"totals": totals, "recent": recent}
        return Response(CPPRPApplicationsOverviewSerializer(payload).data)
