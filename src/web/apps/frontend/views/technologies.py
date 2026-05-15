from apps.frontend.decorators import moderator_required
from apps.frontend.utils import LOGIN_URL
from apps.projects.models import ProjectStatus, Technology, TechnologyStatus
from apps.users.utils import user_is_moderator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST


@login_required(login_url=LOGIN_URL)
def technology_list(request):
    live_filter = Q(projects__status__in=ProjectStatus.catalog_values())

    approved_list = list(
        Technology.objects.approved()
        .annotate(project_count=Count("projects", filter=live_filter, distinct=True))
        .order_by("-project_count", "normalized_name")
    )

    is_mod = user_is_moderator(request.user)
    pending_list = (
        list(
            Technology.objects.filter(status=TechnologyStatus.PENDING)
            .annotate(project_count=Count("projects", filter=live_filter, distinct=True))
            .order_by("-project_count", "normalized_name")
        )
        if is_mod
        else []
    )

    return render(
        request,
        "frontend/technology_list.html",
        {
            "approved_technologies": approved_list,
            "pending_technologies": pending_list,
            "is_moderator": is_mod,
            "total_approved": len(approved_list),
        },
    )


@login_required(login_url=LOGIN_URL)
@moderator_required
@require_POST
def technology_moderate(request, pk):
    tech = get_object_or_404(Technology, pk=pk, status=TechnologyStatus.PENDING)
    action = request.POST.get("action", "").strip()

    if action == "approve":
        tech.status = TechnologyStatus.APPROVED
        tech.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Технология «{tech.name}» одобрена.")
    elif action == "reject":
        tech.status = TechnologyStatus.REJECTED
        tech.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Технология «{tech.name}» отклонена.")
    else:
        messages.error(request, "Неизвестное действие.")

    return redirect("frontend:technology_list")
