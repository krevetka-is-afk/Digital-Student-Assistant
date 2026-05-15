from apps.applications.models import Application, ApplicationStatus
from apps.applications.services import review_application_service
from apps.frontend.forms import ApplicationFilterForm, ReviewApplicationForm
from apps.frontend.utils import LOGIN_URL, flash_form_errors
from apps.projects.models import Project, ProjectStatus
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from ..projects import PAGE_SIZE


@login_required(login_url=LOGIN_URL)
def application_list(request):
    return redirect(reverse("frontend:project_list") + "?tab=applications")

@login_required(login_url=LOGIN_URL)
def project_applications(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)

    if project.owner != request.user and not request.user.is_staff:
        raise Http404

    filter_form   = ApplicationFilterForm(request.GET)
    filter_form.is_valid()
    status_filter = filter_form.cleaned_data.get("status", "")
    page_number   = request.GET.get("page", 1)

    queryset = (
        Application.objects
        .filter(project=project)
        .select_related("applicant", "reviewed_by")
        .order_by("-created_at")
    )
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    paginator = Paginator(queryset, PAGE_SIZE)
    page_obj  = paginator.get_page(page_number)

    counts = Application.objects.filter(project=project).aggregate(
        total=Count("pk"),
        submitted=Count("pk", filter=Q(status=ApplicationStatus.SUBMITTED)),
        accepted=Count("pk",  filter=Q(status=ApplicationStatus.ACCEPTED)),
        rejected=Count("pk",  filter=Q(status=ApplicationStatus.REJECTED)),
    )

    return render(request, "frontend/project_applications.html", {
        "project":           project,
        "page_obj":          page_obj,
        "status_filter":     status_filter,
        "filter_form":       filter_form,
        "ApplicationStatus": ApplicationStatus,
        "ProjectStatus":     ProjectStatus,
        "counts":            counts,
        "total_count":       counts["total"],
        "spots_left":        max(0, project.team_size - project.accepted_participants_count),
    })

@login_required(login_url=LOGIN_URL)
@require_POST
def review_application_view(request, pk):
    application = get_object_or_404(
        Application.objects.select_related("project", "project__owner"),
        pk=pk,
    )

    if application.project.owner != request.user and not request.user.is_staff:
        raise PermissionDenied

    form = ReviewApplicationForm(request.POST)
    if not form.is_valid():
        flash_form_errors(request, form)
        return redirect("frontend:project_applications", pk=application.project.pk)

    decision = form.cleaned_data["decision"]
    comment  = form.cleaned_data["comment"]

    try:
        review_application_service(application, request.user, decision, comment)
        messages.success(
            request,
            "Заявка принята!" if decision == "accept" else "Заявка отклонена.",
        )
    except DRFPermissionDenied:
        messages.error(request, "У вас нет прав для этого действия.")
    except DRFValidationError:
        messages.error(request, "Заявка не может быть обработана — её статус уже изменился.")

    return redirect("frontend:project_applications", pk=application.project.pk)
