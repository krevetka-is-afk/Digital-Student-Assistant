"""
Student personal dashboard (overview) view.

Aggregates the student's activity in one place:
  - counters (applications by status, favorites)
  - recent applications
  - bookmarked projects
  - active platform deadlines
  - active document templates
"""

import logging

from apps.account.models import DeadlineAudience, DocumentTemplate, PlatformDeadline
from apps.applications.models import Application, ApplicationStatus
from apps.frontend.decorators import student_required
from apps.projects.models import Project, ProjectStatus
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

logger = logging.getLogger(__name__)

_RECENT_APPS_COUNT = 5
_RECENT_FAV_COUNT = 6


@login_required(login_url="/auth/")
@student_required
def student_overview(request):
    """Personal dashboard for the student role."""
    user = request.user

    # ── 1. Applications ──────────────────────────────────────────────────────
    all_apps = (
        Application.objects.filter(applicant=user)
        .select_related("project")
        .order_by("-created_at")
    )
    counters = {
        "total": all_apps.count(),
        "submitted": all_apps.filter(status=ApplicationStatus.SUBMITTED).count(),
        "accepted": all_apps.filter(status=ApplicationStatus.ACCEPTED).count(),
        "rejected": all_apps.filter(status=ApplicationStatus.REJECTED).count(),
    }
    recent_apps = list(all_apps[:_RECENT_APPS_COUNT])

    # ── 2. Favourite projects ─────────────────────────────────────────────────
    try:
        fav_ids = user.profile.get_favorite_project_ids()
    except Exception:
        fav_ids = []

    counters["favorites"] = len(fav_ids)
    fav_projects = []
    if fav_ids:
        fav_projects = list(
            Project.objects.filter(pk__in=fav_ids[:_RECENT_FAV_COUNT])
            .select_related("owner")
            .order_by("-updated_at")
        )

    # ── 3. Platform deadlines for students ────────────────────────────────────
    deadlines = list(
        PlatformDeadline.objects.filter(
            is_active=True,
            audience__in=[DeadlineAudience.GLOBAL, DeadlineAudience.STUDENT],
        ).order_by("ends_at", "title")
    )

    # ── 4. Document templates for students ───────────────────────────────────
    templates = list(
        DocumentTemplate.objects.filter(
            is_active=True,
            audience__in=[DeadlineAudience.GLOBAL, DeadlineAudience.STUDENT],
        ).order_by("title")
    )

    context = {
        "counters": counters,
        "recent_apps": recent_apps,
        "fav_projects": fav_projects,
        "fav_ids_total": len(fav_ids),
        "deadlines": deadlines,
        "templates": templates,
        "ApplicationStatus": ApplicationStatus,
        "ProjectStatus": ProjectStatus,
    }
    return render(request, "frontend/student_overview.html", context)
