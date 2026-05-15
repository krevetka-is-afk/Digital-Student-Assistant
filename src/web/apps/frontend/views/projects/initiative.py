from apps.frontend.decorators import moderator_required, student_required
from apps.frontend.forms import InitiativeProjectForm, InitiativeProposalModerationForm
from apps.frontend.utils import LOGIN_URL, flash_form_errors
from apps.projects.initiative_models import InitiativeProposal, InitiativeProposalStatus
from apps.projects.initiative_transitions import (
    moderate_initiative_proposal,
    submit_initiative_proposal_for_moderation,
)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework.exceptions import ValidationError as DRFValidationError

_PAGE_SIZE = 9
_EDITABLE_STATUSES = {InitiativeProposalStatus.DRAFT, InitiativeProposalStatus.REVISION_REQUESTED}

@login_required(login_url=LOGIN_URL)
@student_required
def initiative_project_create(request):
    if request.method == "POST":
        form = InitiativeProjectForm(request.POST)
        if form.is_valid():
            proposal = InitiativeProposal.objects.create(
                owner=request.user,
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                tech_tags=form.cleaned_data["tech_tags_raw"],
                team_size=form.cleaned_data["team_size"],
                supervisor_name=form.cleaned_data["supervisor_name"],
            )
            proposal.sync_technologies()
            messages.success(
                request,
                "Черновик создан. Проверьте данные и отправьте на модерацию.",
            )
            return redirect("frontend:initiative_proposal_list")
        tags_initial = request.POST.get("tech_tags_raw", "")
    else:
        tags_initial = ""
        form = InitiativeProjectForm()

    return render(request, "frontend/initiative_form.html", {
        "form":         form,
        "tags_initial": tags_initial,
    })

@login_required(login_url=LOGIN_URL)
@student_required
def initiative_proposal_list(request):
    page_number = request.GET.get("page", 1)
    queryset = (
        InitiativeProposal.objects
        .filter(owner=request.user)
        .select_related("published_project")
        .order_by("-updated_at")
    )
    paginator = Paginator(queryset, _PAGE_SIZE)
    page_obj  = paginator.get_page(page_number)
    return render(request, "frontend/initiative_list.html", {
        "page_obj":                 page_obj,
        "InitiativeProposalStatus": InitiativeProposalStatus,
        "editable_statuses":        _EDITABLE_STATUSES,
    })

@login_required(login_url=LOGIN_URL)
@student_required
def initiative_proposal_edit(request, pk):
    proposal = get_object_or_404(
        InitiativeProposal.objects.select_related("owner"),
        pk=pk,
    )
    if proposal.owner != request.user:
        raise PermissionDenied

    if proposal.status not in _EDITABLE_STATUSES:
        messages.error(
            request,
            "Редактирование недоступно — предложение уже отправлено или опубликовано.",
        )
        return redirect("frontend:initiative_proposal_list")

    if request.method == "POST":
        form = InitiativeProjectForm(request.POST)
        if form.is_valid():
            proposal.title           = form.cleaned_data["title"]
            proposal.description     = form.cleaned_data["description"]
            proposal.tech_tags       = form.cleaned_data["tech_tags_raw"]
            proposal.team_size       = form.cleaned_data["team_size"]
            proposal.supervisor_name = form.cleaned_data["supervisor_name"]
            proposal.save(update_fields=[
                "title", "description", "tech_tags",
                "team_size", "supervisor_name", "updated_at",
            ])
            proposal.sync_technologies()
            messages.success(request, "Данные сохранены.")
            return redirect("frontend:initiative_proposal_list")
        tags_initial = request.POST.get("tech_tags_raw", "")
    else:
        tags_initial = ", ".join(proposal.tech_tags) if proposal.tech_tags else ""
        form = InitiativeProjectForm(initial={
            "title":           proposal.title,
            "description":     proposal.description,
            "tech_tags_raw":   tags_initial,
            "team_size":       proposal.team_size,
            "supervisor_name": proposal.supervisor_name,
        })

    return render(request, "frontend/initiative_edit.html", {
        "form":         form,
        "proposal":     proposal,
        "tags_initial": tags_initial,
    })

@require_POST
@login_required(login_url=LOGIN_URL)
@student_required
def initiative_proposal_submit(request, pk):
    proposal = get_object_or_404(InitiativeProposal, pk=pk)
    if proposal.owner != request.user:
        raise PermissionDenied
    try:
        submit_initiative_proposal_for_moderation(proposal, request.user)
        messages.success(request, f"Предложение «{proposal.title}» отправлено на модерацию.")
    except DRFValidationError:
        messages.error(request, "Нельзя отправить предложение в текущем статусе.")
    return redirect("frontend:initiative_proposal_list")

@require_POST
@login_required(login_url=LOGIN_URL)
@student_required
def initiative_proposal_delete(request, pk):
    proposal = get_object_or_404(InitiativeProposal, pk=pk)
    if proposal.owner != request.user:
        raise PermissionDenied
    if proposal.status not in _EDITABLE_STATUSES:
        messages.error(request, "Удалить можно только черновик или возвращённое предложение.")
        return redirect("frontend:initiative_proposal_list")
    title = proposal.title
    proposal.delete()
    messages.success(request, f"Предложение «{title}» удалено.")
    return redirect("frontend:initiative_proposal_list")

@login_required(login_url=LOGIN_URL)
@moderator_required
def initiative_moderation_detail(request, pk):
    from apps.projects.initiative_models import InitiativeProposalSubmission
    proposal = get_object_or_404(
        InitiativeProposal.objects
        .select_related("owner", "moderated_by")
        .prefetch_related(
            models.Prefetch(
                "submissions",
                queryset=InitiativeProposalSubmission.objects
                    .select_related("submitted_by", "reviewed_by")
                    .order_by("-submission_number"),
            )
        ),
        pk=pk,
        status=InitiativeProposalStatus.ON_MODERATION,
    )
    return render(request, "frontend/initiative_moderation_detail.html", {
        "proposal": proposal,
    })

@login_required(login_url=LOGIN_URL)
@moderator_required
def initiative_moderation_list(request):
    page_number = request.GET.get("page", 1)
    queryset = (
        InitiativeProposal.objects
        .filter(status=InitiativeProposalStatus.ON_MODERATION)
        .select_related("owner")
        .order_by("updated_at")
    )
    paginator   = Paginator(queryset, _PAGE_SIZE)
    page_obj    = paginator.get_page(page_number)
    queue_count = paginator.count
    return render(request, "frontend/initiative_moderation_list.html", {
        "page_obj":    page_obj,
        "queue_count": queue_count,
    })

@require_POST
@login_required(login_url=LOGIN_URL)
@moderator_required
def initiative_moderate_decide(request, pk):
    proposal = get_object_or_404(InitiativeProposal, pk=pk)
    form = InitiativeProposalModerationForm(request.POST)
    if not form.is_valid():
        flash_form_errors(request, form)
        return redirect("frontend:initiative_moderation_list")
    decision = form.cleaned_data["decision"]
    comment  = form.cleaned_data["comment"]
    try:
        moderate_initiative_proposal(proposal, request.user, decision, comment)
        if decision == "approve":
            messages.success(request, f"Инициатива «{proposal.title}» одобрена и опубликована!")
        else:
            messages.success(request, f"Инициатива «{proposal.title}» отклонена.")
    except DRFValidationError:
        messages.error(
            request,
            "Предложение уже прошло модерацию или находится в недопустимом статусе.",
        )
    return redirect("frontend:initiative_moderation_list")
