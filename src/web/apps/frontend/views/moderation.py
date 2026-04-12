from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.projects.models import Project, ProjectStatus
from apps.users.utils import user_is_moderator

from .projects import PAGE_SIZE


# ---------------------------------------------------------------------------
# Moderation Queue (CPPRP/staff: review projects awaiting moderation)
# ---------------------------------------------------------------------------

@login_required(login_url="/auth/")
def moderation_list(request):
    """CPPRP/staff moderator sees all projects waiting for moderation."""
    if not (request.user.is_staff or user_is_moderator(request.user)):
        raise Http404

    page_number = request.GET.get("page", 1)
    queryset = (
        Project.objects
        .filter(status=ProjectStatus.ON_MODERATION)
        .select_related("owner")
        .order_by("updated_at")  # FIFO — oldest first
    )

    paginator   = Paginator(queryset, PAGE_SIZE)
    page_obj    = paginator.get_page(page_number)
    queue_count = queryset.count()

    context = {
        "page_obj":      page_obj,
        "ProjectStatus": ProjectStatus,
        "queue_count":   queue_count,
    }
    return render(request, "frontend/moderation_list.html", context)


@require_POST
@login_required(login_url="/auth/")
def moderate_project_decide(request, pk):
    """CPPRP/staff approves or rejects a project in moderation."""
    from apps.projects.transitions import moderate_project
    from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError

    project  = get_object_or_404(Project, pk=pk)
    decision = request.POST.get("decision", "").strip()
    comment  = request.POST.get("comment", "").strip()

    try:
        moderate_project(project, request.user, decision, comment)
        if decision == "approve":
            messages.success(request, f"Проект «{project.title}» опубликован!")
        else:
            messages.success(request, f"Проект «{project.title}» отклонён.")
    except PermissionDenied:
        messages.error(request, "У вас нет прав для модерации.")
    except DRFValidationError as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            msg = next(iter(detail.values()))
            if isinstance(msg, list):
                msg = msg[0]
        else:
            msg = str(detail)
        messages.error(request, f"Ошибка: {msg}")

    return redirect("frontend:moderation_list")
