from apps.account.models import DeadlineAudience, DocumentTemplate, PlatformDeadline
from apps.applications.models import Application, ApplicationStatus
from apps.frontend.decorators import student_required
from apps.frontend.utils import LOGIN_URL
from apps.projects.initiative_models import InitiativeProposal, InitiativeProposalStatus
from apps.projects.models import Project, ProjectStatus
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

_RECENT_APPS = 5
_RECENT_FAVS = 6


@login_required(login_url=LOGIN_URL)
@student_required
def student_overview(request):
    user = request.user

    base_qs = Application.objects.filter(applicant=user)
    counters = base_qs.aggregate(
        total=Count("pk"),
        submitted=Count("pk", filter=Q(status=ApplicationStatus.SUBMITTED)),
        accepted=Count("pk", filter=Q(status=ApplicationStatus.ACCEPTED)),
        rejected=Count("pk", filter=Q(status=ApplicationStatus.REJECTED)),
    )
    recent_apps = list(base_qs.select_related("project").order_by("-created_at")[:_RECENT_APPS])

    _profile = getattr(user, "profile", None)
    fav_ids = list(_profile.favorite_project_ids or [] if _profile else [])
    favorites_count = len(fav_ids)

    fav_projects = (
        list(
            Project.objects.filter(pk__in=fav_ids[:_RECENT_FAVS])
            .select_related("owner")
            .order_by("-updated_at")
        )
        if fav_ids
        else []
    )

    deadlines = list(
        PlatformDeadline.objects.filter(
            is_active=True,
            audience__in=[DeadlineAudience.GLOBAL, DeadlineAudience.STUDENT],
        ).order_by("ends_at", "title")
    )
    templates = list(
        DocumentTemplate.objects.filter(
            is_active=True,
            audience__in=[DeadlineAudience.GLOBAL, DeadlineAudience.STUDENT],
        ).order_by("title")
    )

    initiatives = list(InitiativeProposal.objects.filter(owner=user).order_by("-updated_at")[:3])

    return render(
        request,
        "frontend/student_overview.html",
        {
            "counters": {**counters, "favorites": favorites_count},
            "recent_apps": recent_apps,
            "fav_projects": fav_projects,
            "deadlines": deadlines,
            "templates": templates,
            "initiatives": initiatives,
            "InitiativeProposalStatus": InitiativeProposalStatus,
            "ApplicationStatus": ApplicationStatus,
            "ProjectStatus": ProjectStatus,
        },
    )
