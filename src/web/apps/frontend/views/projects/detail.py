from apps.applications.models import Application, ApplicationStatus
from apps.frontend.utils import LOGIN_URL
from apps.projects.models import Project, ProjectStatus
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render


@login_required(login_url=LOGIN_URL)
def project_detail(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)

    is_owner = project.owner == request.user
    is_public = project.status in ProjectStatus.catalog_values()

    if not is_public and not is_owner and not request.user.is_staff:
        raise PermissionDenied

    application = None
    if not is_owner:
        application = Application.objects.filter(
            project=project,
            applicant=request.user,
        ).first()

    spots_left = max(0, project.team_size - project.accepted_participants_count)

    return render(
        request,
        "frontend/project_detail.html",
        {
            "project": project,
            "application": application,
            "is_owner": is_owner,
            "spots_left": spots_left,
            "ApplicationStatus": ApplicationStatus,
            "ProjectStatus": ProjectStatus,
        },
    )
