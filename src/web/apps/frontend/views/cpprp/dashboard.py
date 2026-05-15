from apps.account.models import DeadlineAudience, DocumentTemplate, PlatformDeadline
from apps.applications.models import Application, ApplicationStatus
from apps.frontend.decorators import moderator_required
from apps.frontend.forms import DeadlineForm, ExternalAllowlistBulkForm, TemplateForm
from apps.frontend.utils import LOGIN_URL
from apps.projects.models import Project, ProjectStatus
from apps.users.models import (
    ExternalAccessAllowlist,
    ExternalAccessRequest,
    ExternalAccessRequestStatus,
    UserProfile,
    UserRole,
)
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

_APPS_PAGE_SIZE = 20


def _cpprp_tab_redirect(tab: str) -> HttpResponse:
    return redirect(reverse("frontend:cpprp_dashboard") + f"?tab={tab}")


@login_required(login_url=LOGIN_URL)
@moderator_required
def cpprp_dashboard(request):
    project_counts = Project.objects.aggregate(
        **{
            s: Count("pk", filter=Q(status=s))
            for s in [
                ProjectStatus.PUBLISHED,
                ProjectStatus.ON_MODERATION,
                ProjectStatus.STAFFED,
                ProjectStatus.DRAFT,
            ]
        }
    )

    app_totals = Application.objects.aggregate(
        total=Count("pk"),
        submitted=Count("pk", filter=Q(status=ApplicationStatus.SUBMITTED)),
        accepted=Count("pk", filter=Q(status=ApplicationStatus.ACCEPTED)),
        rejected=Count("pk", filter=Q(status=ApplicationStatus.REJECTED)),
    )

    active_students_count = (
        Application.objects.filter(status=ApplicationStatus.ACCEPTED)
        .values("applicant_id")
        .distinct()
        .count()
    )
    total_students_count = UserProfile.objects.filter(role=UserRole.STUDENT).count()

    app_status_filter = request.GET.get("status", "").strip()
    app_page = request.GET.get("page", 1)

    apps_qs = Application.objects.select_related("applicant", "project").order_by("-created_at")
    if app_status_filter and app_status_filter in ApplicationStatus.values:
        apps_qs = apps_qs.filter(status=app_status_filter)

    apps_paginator = Paginator(apps_qs, _APPS_PAGE_SIZE)
    apps_page_obj = apps_paginator.get_page(app_page)

    deadlines = list(PlatformDeadline.objects.order_by("ends_at", "title"))
    templates = list(DocumentTemplate.objects.order_by("title"))
    external_pending_requests = list(
        ExternalAccessRequest.objects.filter(status=ExternalAccessRequestStatus.PENDING).order_by(
            "created_at"
        )
    )
    external_recent_requests = list(
        ExternalAccessRequest.objects.select_related("reviewed_by").order_by("-updated_at")[:20]
    )
    external_allowlist = list(
        ExternalAccessAllowlist.objects.select_related("approved_by").order_by("email")[:50]
    )

    return render(
        request,
        "frontend/cpprp_dashboard.html",
        {
            "project_counts": project_counts,
            "app_totals": app_totals,
            "active_students_count": active_students_count,
            "total_students_count": total_students_count,
            "apps_page_obj": apps_page_obj,
            "app_status_filter": app_status_filter,
            "deadlines": deadlines,
            "deadline_form": DeadlineForm(),
            "templates": templates,
            "template_form": TemplateForm(),
            "external_pending_requests": external_pending_requests,
            "external_recent_requests": external_recent_requests,
            "external_allowlist": external_allowlist,
            "external_allowlist_form": ExternalAllowlistBulkForm(),
            "ApplicationStatus": ApplicationStatus,
            "ProjectStatus": ProjectStatus,
            "DeadlineAudience": DeadlineAudience,
            "ExternalAccessRequestStatus": ExternalAccessRequestStatus,
        },
    )
