import json

from apps.account.permissions import has_any_role
from apps.applications.models import Application, ApplicationStatus
from apps.projects.models import Project, ProjectStatus
from apps.users.models import UserRole
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .projects import PAGE_SIZE


def _project_accepts_applications(project: Project) -> bool:
    return (
        project.status == ProjectStatus.PUBLISHED
        and project.accepted_participants_count < project.team_size
    )


# ---------------------------------------------------------------------------
# Apply (card quick-apply)
# ---------------------------------------------------------------------------

@require_POST
def apply_to_project(request, pk):
    """Quick-apply from project list card (no motivation field)."""
    if not request.user.is_authenticated:
        return redirect("/auth/?next=/projects/")
    if not has_any_role(request.user, allowed={UserRole.STUDENT}, allow_staff=False):
        return HttpResponseBadRequest("Подавать заявки могут только студенты.")

    project = get_object_or_404(Project, pk=pk)

    if not _project_accepts_applications(project):
        return HttpResponseBadRequest("Project is not accepting applications.")

    existing = Application.objects.filter(project=project, applicant=request.user).first()
    if not existing:
        existing = Application.objects.create(
            project=project,
            applicant=request.user,
            status=ApplicationStatus.SUBMITTED,
        )

    ctx = {
        "project":           project,
        "application_status": existing.status,
        "ApplicationStatus": ApplicationStatus,
        "ProjectStatus":     ProjectStatus,
    }
    return render(request, "frontend/partials/apply_button.html", ctx)


# ---------------------------------------------------------------------------
# Submit Application (detail page, with motivation modal)
# ---------------------------------------------------------------------------

@require_POST
def submit_application(request, pk):
    """
    Submit application with motivation text from project detail modal.
    Returns HTMX partial that replaces the apply action area.
    """
    if not request.user.is_authenticated:
        if request.headers.get("HX-Request"):
            # HTMX: instruct client to redirect
            response = HttpResponse(status=204)
            response["HX-Redirect"] = f"/auth/?next=/projects/{pk}/"
            return response
        # fetch() call from the shared apply modal — return JSON so JS can handle it cleanly
        from django.http import JsonResponse
        return JsonResponse({"error": "unauthenticated", "redirect": "/auth/"}, status=401)
    if not has_any_role(request.user, allowed={UserRole.STUDENT}, allow_staff=False):
        return HttpResponseBadRequest("Подавать заявки могут только студенты.")

    project = get_object_or_404(Project, pk=pk)

    if not _project_accepts_applications(project):
        return HttpResponseBadRequest("Project is not accepting applications.")

    motivation = request.POST.get("motivation", "").strip()

    application, created = Application.objects.get_or_create(
        project=project,
        applicant=request.user,
        defaults={
            "motivation": motivation,
            "status":     ApplicationStatus.SUBMITTED,
        },
    )

    toast_msg = (
        "Заявка успешно отправлена!" if created else "Вы уже подавали заявку на этот проект."
    )
    toast_type = "success" if created else "info"

    # source=card   → compact button partial (project list cards)
    # source=detail → full apply action partial (project detail page)
    source = request.POST.get("source", "detail")

    if source == "card":
        ctx = {
            "project":            project,
            "application_status": application.status,
            "ApplicationStatus":  ApplicationStatus,
            "ProjectStatus":      ProjectStatus,
        }
        response = render(request, "frontend/partials/apply_button.html", ctx)
    else:
        ctx = {
            "project":           project,
            "application":       application,
            "is_owner":          False,
            "ApplicationStatus": ApplicationStatus,
            "ProjectStatus":     ProjectStatus,
        }
        response = render(request, "frontend/partials/apply_action_detail.html", ctx)

    response["HX-Trigger"] = json.dumps({"showToast": {"message": toast_msg, "type": toast_type}})
    return response


# ---------------------------------------------------------------------------
# Application List (student: my applications)
# ---------------------------------------------------------------------------

@login_required(login_url="/auth/")
def application_list(request):
    """Legacy standalone page — redirect to the Applications tab in /projects/."""
    from django.urls import reverse
    return redirect(reverse("frontend:project_list") + "?tab=applications")


# ---------------------------------------------------------------------------
# Project Applications (customer: review applications to their project)
# ---------------------------------------------------------------------------

@login_required(login_url="/auth/")
def project_applications(request, pk):
    """Project owner sees all applications to their project and can accept/reject."""
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)

    if project.owner != request.user and not request.user.is_staff:
        raise Http404

    status_filter = request.GET.get("status", "").strip()
    page_number   = request.GET.get("page", 1)

    queryset = (
        Application.objects
        .filter(project=project)
        .select_related("applicant")
        .order_by("-created_at")
    )

    if status_filter:
        queryset = queryset.filter(status=status_filter)

    paginator = Paginator(queryset, PAGE_SIZE)
    page_obj  = paginator.get_page(page_number)

    base_qs = Application.objects.filter(project=project)
    counts  = {
        "submitted": base_qs.filter(status=ApplicationStatus.SUBMITTED).count(),
        "accepted":  base_qs.filter(status=ApplicationStatus.ACCEPTED).count(),
        "rejected":  base_qs.filter(status=ApplicationStatus.REJECTED).count(),
    }

    context = {
        "project":           project,
        "page_obj":          page_obj,
        "status_filter":     status_filter,
        "ApplicationStatus": ApplicationStatus,
        "ProjectStatus":     ProjectStatus,
        "counts":            counts,
        "total_count":       sum(counts.values()),
        "spots_left":        max(0, project.team_size - project.accepted_participants_count),
    }
    return render(request, "frontend/project_applications.html", context)


# ---------------------------------------------------------------------------
# Review Application (accept / reject)
# ---------------------------------------------------------------------------

@require_POST
@login_required(login_url="/auth/")
def review_application_view(request, pk):
    """Accept or reject an application (project owner / staff)."""
    from apps.applications.transitions import review_application
    from rest_framework.exceptions import PermissionDenied
    from rest_framework.exceptions import ValidationError as DRFValidationError

    application = get_object_or_404(
        Application.objects.select_related("project", "project__owner"),
        pk=pk,
    )
    decision = request.POST.get("decision", "").strip()
    comment  = request.POST.get("comment", "").strip()

    try:
        review_application(application, request.user, decision, comment)
        if decision == "accept":
            messages.success(request, "Заявка принята!")
        else:
            messages.success(request, "Заявка отклонена.")
    except PermissionDenied:
        messages.error(request, "У вас нет прав для этого действия.")
    except DRFValidationError as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            msg = next(iter(detail.values()))
            if isinstance(msg, list):
                msg = msg[0]
        else:
            msg = str(detail)
        messages.error(request, f"Ошибка: {msg}")

    return redirect("frontend:project_applications", pk=application.project.pk)


# ---------------------------------------------------------------------------
# Withdraw Application (student cancels their own SUBMITTED application)
# ---------------------------------------------------------------------------

@require_POST
@login_required(login_url="/auth/")
def withdraw_application(request, pk):
    """Student withdraws their own submitted application."""
    application = get_object_or_404(
        Application.objects.select_related("project"),
        pk=pk,
    )

    if application.applicant != request.user:
        raise PermissionDenied

    if application.status != ApplicationStatus.SUBMITTED:
        messages.error(request, "Отозвать можно только заявку со статусом «На рассмотрении».")
        return redirect("frontend:project_list")

    project_title = application.project.title
    application.delete()
    messages.success(request, f"Заявка на проект «{project_title}» отозвана.")
    return redirect("frontend:project_list")


# ---------------------------------------------------------------------------
# Edit Application (student updates motivation on their own SUBMITTED application)
# ---------------------------------------------------------------------------

@login_required(login_url="/auth/")
def edit_application(request, pk):
    """Student updates motivation text on their own submitted application."""
    application = get_object_or_404(
        Application.objects.select_related("project"),
        pk=pk,
    )

    if application.applicant != request.user:
        raise PermissionDenied

    if application.status != ApplicationStatus.SUBMITTED:
        messages.error(request, "Редактировать можно только заявку со статусом «На рассмотрении».")
        return redirect("frontend:project_list")

    if request.method == "POST":
        motivation = request.POST.get("motivation", "").strip()
        application.motivation = motivation
        application.save(update_fields=["motivation"])
        messages.success(request, "Мотивация обновлена.")
        return redirect("frontend:project_list")

    return render(
        request,
        "frontend/edit_application.html",
        {
            "application": application,
            "project": application.project,
        },
    )
