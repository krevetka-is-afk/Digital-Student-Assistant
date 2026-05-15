from apps.frontend.decorators import customer_required
from apps.frontend.forms import ProjectFrontendForm
from apps.frontend.utils import LOGIN_URL
from apps.projects.models import Project, ProjectStatus
from apps.projects.transitions import submit_project_for_moderation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework.exceptions import ValidationError as DRFValidationError

_LOCKED_STATUSES    = {ProjectStatus.PUBLISHED, ProjectStatus.STAFFED, ProjectStatus.ARCHIVED}
_DELETABLE_STATUSES = {ProjectStatus.DRAFT, ProjectStatus.REJECTED}

@login_required(login_url=LOGIN_URL)
@customer_required
def project_create(request):
    if request.method == "POST":
        form = ProjectFrontendForm(request.POST)
        if form.is_valid():
            project = Project.objects.create(
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                tech_tags=form.cleaned_data["tech_tags_raw"],
                team_size=form.cleaned_data["team_size"],
                work_format=form.cleaned_data["work_format"] or "",
                hours_per_week=form.cleaned_data["hours_per_week"],
                is_paid=form.cleaned_data["is_paid"],
                application_deadline=form.cleaned_data["application_deadline"],
                selection_criteria=form.cleaned_data["selection_criteria"] or "",
                supervisor_name=form.cleaned_data["supervisor_name"] or "",
                supervisor_email=form.cleaned_data["supervisor_email"] or "",
                supervisor_department=form.cleaned_data["supervisor_department"] or "",
                owner=request.user,
                status=ProjectStatus.DRAFT,
            )
            messages.success(request, "Проект создан!")
            return redirect("frontend:project_detail", pk=project.pk)
    else:
        form = ProjectFrontendForm()

    return render(request, "frontend/project_form.html", {
        "form":        form,
        "is_create":   True,
        "tags_initial": "",
    })

@login_required(login_url=LOGIN_URL)
def project_edit(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)

    if project.owner != request.user and not request.user.is_staff:
        raise PermissionDenied

    if project.status in _LOCKED_STATUSES:
        messages.error(
            request,
            f"Редактирование недоступно — проект имеет статус «{project.get_status_display()}».",
        )
        return redirect("frontend:project_detail", pk=project.pk)

    if request.method == "POST":
        form = ProjectFrontendForm(request.POST)
        if form.is_valid():
            project.title               = form.cleaned_data["title"]
            project.description         = form.cleaned_data["description"]
            project.tech_tags           = form.cleaned_data["tech_tags_raw"]
            project.team_size           = form.cleaned_data["team_size"]
            project.work_format         = form.cleaned_data["work_format"] or ""
            project.hours_per_week      = form.cleaned_data["hours_per_week"]
            project.is_paid             = form.cleaned_data["is_paid"]
            project.application_deadline = form.cleaned_data["application_deadline"]
            project.selection_criteria  = form.cleaned_data["selection_criteria"] or ""
            project.supervisor_name      = form.cleaned_data["supervisor_name"] or ""
            project.supervisor_email     = form.cleaned_data["supervisor_email"] or ""
            project.supervisor_department = form.cleaned_data["supervisor_department"] or ""
            project.save(
                update_fields=[
                    "title", "description", "tech_tags", "team_size",
                    "work_format", "hours_per_week", "is_paid",
                    "application_deadline", "selection_criteria",
                    "supervisor_name", "supervisor_email", "supervisor_department",
                    "updated_at",
                ]
            )
            messages.success(request, "Проект сохранён!")
            return redirect("frontend:project_detail", pk=project.pk)
        tags_initial = request.POST.get("tech_tags_raw", "")
    else:
        tags_initial = ", ".join(project.tech_tags) if project.tech_tags else ""
        form = ProjectFrontendForm(initial={
            "title":                project.title,
            "description":          project.description,
            "tech_tags_raw":        tags_initial,
            "team_size":            project.team_size,
            "work_format":          project.work_format,
            "hours_per_week":       project.hours_per_week,
            "is_paid": (
                "yes" if project.is_paid is True else "no" if project.is_paid is False else ""
            ),
            "application_deadline": project.application_deadline,
            "selection_criteria":   project.selection_criteria,
            "supervisor_name":      project.supervisor_name,
            "supervisor_email":     project.supervisor_email,
            "supervisor_department": project.supervisor_department,
        })

    return render(request, "frontend/project_form.html", {
        "form":        form,
        "project":     project,
        "is_create":   False,
        "tags_initial": tags_initial,
    })

@require_POST
@login_required(login_url=LOGIN_URL)
def project_submit_moderation(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if project.owner != request.user and not request.user.is_staff:
        raise PermissionDenied

    try:
        submit_project_for_moderation(project, request.user)
        messages.success(request, "Проект отправлен на модерацию!")
    except DRFValidationError:
        messages.error(request, "Нельзя отправить проект на модерацию в текущем статусе.")
    return redirect("frontend:project_detail", pk=project.pk)

@require_POST
@login_required(login_url=LOGIN_URL)
def project_delete(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)

    if project.owner != request.user and not request.user.is_staff:
        raise PermissionDenied

    if project.status not in _DELETABLE_STATUSES:
        messages.error(
            request, f"Нельзя удалить проект со статусом «{project.get_status_display()}»."
        )
        return redirect("frontend:project_detail", pk=project.pk)

    title = project.title
    project.delete()
    messages.success(request, f"Проект «{title}» удалён.")
    return redirect("frontend:project_list")
