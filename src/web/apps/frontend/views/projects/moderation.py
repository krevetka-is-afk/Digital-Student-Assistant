from apps.frontend.decorators import moderator_required
from apps.frontend.forms import ModerationDecisionForm, ModerationProjectFieldsForm
from apps.frontend.utils import LOGIN_URL, flash_form_errors
from apps.projects.models import Project, ProjectStatus
from apps.projects.transitions import moderate_project
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework.exceptions import ValidationError as DRFValidationError

_PAGE_SIZE = 9


@login_required(login_url=LOGIN_URL)
@moderator_required
def moderation_list(request):
    page_number = request.GET.get("page", 1)
    queryset = (
        Project.objects.filter(status=ProjectStatus.ON_MODERATION)
        .select_related("owner")
        .order_by("updated_at")
    )
    paginator = Paginator(queryset, _PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    queue_count = paginator.count

    return render(
        request,
        "frontend/moderation_list.html",
        {
            "page_obj": page_obj,
            "ProjectStatus": ProjectStatus,
            "queue_count": queue_count,
        },
    )


@login_required(login_url=LOGIN_URL)
@moderator_required
def moderation_detail(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("owner", "moderated_by"),
        pk=pk,
        status=ProjectStatus.ON_MODERATION,
    )
    fields_form = ModerationProjectFieldsForm(
        initial={
            "study_course": project.study_course,
            "education_program": project.education_program,
            "credits": project.credits,
            "activity_type": project.activity_type,
            "control_form": project.control_form,
            "results_presentation_format": project.results_presentation_format,
            "grading_formula": project.grading_formula,
            "student_participation_format": project.student_participation_format,
        }
    )
    decision_form = ModerationDecisionForm()
    return render(
        request,
        "frontend/moderation_detail.html",
        {
            "project": project,
            "fields_form": fields_form,
            "decision_form": decision_form,
        },
    )


@require_POST
@login_required(login_url=LOGIN_URL)
@moderator_required
def moderation_update_fields(request, pk):
    project = get_object_or_404(Project, pk=pk, status=ProjectStatus.ON_MODERATION)
    form = ModerationProjectFieldsForm(request.POST)
    if form.is_valid():
        cd = form.cleaned_data
        project.study_course = cd["study_course"]
        project.education_program = cd["education_program"] or ""
        project.credits = cd["credits"]
        project.activity_type = cd["activity_type"] or ""
        project.control_form = cd["control_form"] or ""
        project.results_presentation_format = cd["results_presentation_format"] or ""
        project.grading_formula = cd["grading_formula"] or ""
        project.student_participation_format = cd["student_participation_format"] or ""
        project.save(
            update_fields=[
                "study_course",
                "education_program",
                "credits",
                "activity_type",
                "control_form",
                "results_presentation_format",
                "grading_formula",
                "student_participation_format",
                "updated_at",
            ]
        )
        messages.success(request, "Поля сохранены.")
    else:
        flash_form_errors(request, form)
    return redirect("frontend:moderation_detail", pk=pk)


@require_POST
@login_required(login_url=LOGIN_URL)
@moderator_required
def moderate_project_decide(request, pk):
    project = get_object_or_404(Project, pk=pk)

    form = ModerationDecisionForm(request.POST)
    if not form.is_valid():
        flash_form_errors(request, form)
        return redirect("frontend:moderation_list")

    decision = form.cleaned_data["decision"]
    comment = form.cleaned_data["comment"]

    try:
        moderate_project(project, request.user, decision, comment)
        if decision == "approve":
            messages.success(request, f"Проект «{project.title}» опубликован!")
        else:
            messages.success(request, f"Проект «{project.title}» отклонён.")
    except DRFValidationError:
        messages.error(
            request,
            "Проект уже прошёл модерацию или находится в недопустимом состоянии.",
        )

    return redirect("frontend:moderation_list")
