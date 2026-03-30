from django import forms as dj_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.applications.models import Application, ApplicationStatus
from apps.projects.models import Project, ProjectStatus
from apps.projects.utils import collect_all_tags
from apps.users.models import UserRole

PAGE_SIZE = 9
RECOMMENDED_COUNT = 4

_LOCKED_STATUSES   = {ProjectStatus.PUBLISHED, ProjectStatus.STAFFED, "archived"}
_DELETABLE_STATUSES = {ProjectStatus.DRAFT, ProjectStatus.REJECTED}


# ---------------------------------------------------------------------------
# Project form (used in create / edit views)
# ---------------------------------------------------------------------------

class ProjectFrontendForm(dj_forms.Form):
    title = dj_forms.CharField(
        max_length=255,
        error_messages={"required": "Название обязательно.", "max_length": "Не более 255 символов."},
    )
    description = dj_forms.CharField(
        widget=dj_forms.Textarea,
        required=False,
    )
    tech_tags_raw = dj_forms.CharField(required=False)
    team_size = dj_forms.IntegerField(
        min_value=1,
        max_value=100,
        error_messages={
            "required":  "Укажите размер команды.",
            "invalid":   "Введите целое число.",
            "min_value": "Минимум 1 участник.",
            "max_value": "Максимум 100 участников.",
        },
    )

    def clean_tech_tags_raw(self):
        raw = self.cleaned_data.get("tech_tags_raw", "")
        if not raw.strip():
            return []
        return [t.strip().lower() for t in raw.split(",") if t.strip()]


# ---------------------------------------------------------------------------
# Project List
# ---------------------------------------------------------------------------

def project_list(request):
    # Customer sees their own projects (all statuses); moderators see the catalog
    if request.user.is_authenticated:
        try:
            _role = request.user.profile.role
        except Exception:
            _role = ""
        if _role == UserRole.CUSTOMER:
            return _customer_project_list(request)

    # Everyone else: public PUBLISHED catalog
    q                = request.GET.get("q", "").strip()
    tech_tags_filter = request.GET.getlist("tech_tags")
    team_size_filter = request.GET.get("team_size", "").strip()
    page_number      = request.GET.get("page", 1)

    queryset = Project.objects.filter(status=ProjectStatus.PUBLISHED).select_related("owner")

    if q:
        queryset = queryset.filter(title__icontains=q)

    for tag in tech_tags_filter:
        if tag:
            queryset = queryset.filter(tech_tags__contains=[tag])

    if team_size_filter:
        try:
            queryset = queryset.filter(team_size=int(team_size_filter))
        except ValueError:
            pass

    queryset  = queryset.order_by("-created_at")
    paginator = Paginator(queryset, PAGE_SIZE)
    page_obj  = paginator.get_page(page_number)

    recommended = []
    is_filtered = bool(q or tech_tags_filter or team_size_filter)
    if not is_filtered and int(page_number) == 1:
        recommended = list(queryset[:RECOMMENDED_COUNT])

    visible_ids     = [p.id for p in page_obj.object_list]
    rec_ids         = [p.id for p in recommended]
    all_visible_ids = list(set(visible_ids + rec_ids))

    user_applications = {}
    if request.user.is_authenticated:
        apps = Application.objects.filter(
            applicant=request.user,
            project_id__in=all_visible_ids,
        ).values("project_id", "status")
        user_applications = {a["project_id"]: a["status"] for a in apps}

    all_tags = collect_all_tags()

    context = {
        "page_obj":          page_obj,
        "recommended":       recommended,
        "query":             q,
        "tech_tags_filter":  tech_tags_filter,
        "team_size_filter":  team_size_filter,
        "user_applications": user_applications,
        "all_tags":          all_tags,
        "is_filtered":       is_filtered,
        "ApplicationStatus": ApplicationStatus,
        "ProjectStatus":     ProjectStatus,
    }

    if request.headers.get("HX-Request") and request.headers.get("HX-Target") == "projects-section":
        return render(request, "frontend/partials/projects_grid.html", context)

    return render(request, "frontend/project_list.html", context)


def _customer_project_list(request):
    """Customer-specific view: all their own projects, all statuses."""
    page_number   = request.GET.get("page", 1)
    status_filter = request.GET.get("status", "").strip()

    queryset = (
        Project.objects
        .filter(owner=request.user)
        .order_by("-created_at")
    )

    if status_filter:
        queryset = queryset.filter(status=status_filter)

    statuses = [
        ProjectStatus.DRAFT, ProjectStatus.ON_MODERATION,
        ProjectStatus.PUBLISHED, ProjectStatus.STAFFED, ProjectStatus.REJECTED,
    ]
    base_qs = Project.objects.filter(owner=request.user)
    counts  = {s: base_qs.filter(status=s).count() for s in statuses}

    paginator = Paginator(queryset, PAGE_SIZE)
    page_obj  = paginator.get_page(page_number)

    return render(request, "frontend/my_projects.html", {
        "page_obj":      page_obj,
        "status_filter": status_filter,
        "ProjectStatus": ProjectStatus,
        "counts":        counts,
        "total_count":   base_qs.count(),
    })


# ---------------------------------------------------------------------------
# Project Detail
# ---------------------------------------------------------------------------

def project_detail(request, pk):
    """
    Shows project detail page.
    Publicly visible for PUBLISHED / STAFFED projects.
    Owner can also see their own project regardless of status.
    """
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)

    is_owner  = request.user.is_authenticated and project.owner == request.user
    is_public = project.status in ProjectStatus.catalog_values()

    if not is_public and not is_owner and not request.user.is_staff:
        raise Http404

    application = None
    if request.user.is_authenticated and not is_owner:
        application = Application.objects.filter(
            project=project,
            applicant=request.user,
        ).first()

    spots_left = max(0, project.team_size - project.accepted_participants_count)

    context = {
        "project":           project,
        "application":       application,
        "is_owner":          is_owner,
        "spots_left":        spots_left,
        "ApplicationStatus": ApplicationStatus,
        "ProjectStatus":     ProjectStatus,
    }
    return render(request, "frontend/project_detail.html", context)


# ---------------------------------------------------------------------------
# Project Create
# ---------------------------------------------------------------------------

@login_required(login_url="/auth/")
def project_create(request):
    try:
        role = request.user.profile.role
    except Exception:
        role = ""
    if role != UserRole.CUSTOMER:
        messages.error(request, "Создавать проекты могут только заказчики.")
        return redirect("frontend:project_list")

    if request.method == "POST":
        form = ProjectFrontendForm(request.POST)
        if form.is_valid():
            project = Project.objects.create(
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                tech_tags=form.cleaned_data["tech_tags_raw"],
                team_size=form.cleaned_data["team_size"],
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


# ---------------------------------------------------------------------------
# Project Edit
# ---------------------------------------------------------------------------

@login_required(login_url="/auth/")
def project_edit(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)

    if project.owner != request.user and not request.user.is_staff:
        raise Http404

    if project.status in _LOCKED_STATUSES:
        messages.error(request, f"Редактирование недоступно — проект имеет статус «{project.get_status_display()}».")
        return redirect("frontend:project_detail", pk=project.pk)

    if request.method == "POST":
        form = ProjectFrontendForm(request.POST)
        if form.is_valid():
            project.title       = form.cleaned_data["title"]
            project.description = form.cleaned_data["description"]
            project.tech_tags   = form.cleaned_data["tech_tags_raw"]
            project.team_size   = form.cleaned_data["team_size"]
            project.save(update_fields=["title", "description", "tech_tags", "team_size", "updated_at"])
            messages.success(request, "Проект сохранён!")
            return redirect("frontend:project_detail", pk=project.pk)
        tags_initial = request.POST.get("tech_tags_raw", "")
    else:
        tags_initial = ", ".join(project.tech_tags) if project.tech_tags else ""
        form = ProjectFrontendForm(initial={
            "title":         project.title,
            "description":   project.description,
            "tech_tags_raw": tags_initial,
            "team_size":     project.team_size,
        })

    return render(request, "frontend/project_form.html", {
        "form":         form,
        "project":      project,
        "is_create":    False,
        "tags_initial": tags_initial,
    })


# ---------------------------------------------------------------------------
# Submit project for moderation
# ---------------------------------------------------------------------------

@require_POST
@login_required(login_url="/auth/")
def project_submit_moderation(request, pk):
    from apps.projects.transitions import submit_project_for_moderation
    from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError

    project = get_object_or_404(Project, pk=pk)
    try:
        submit_project_for_moderation(project, request.user)
        messages.success(request, "Проект отправлен на модерацию!")
    except (PermissionDenied, DRFValidationError):
        messages.error(request, "Нельзя отправить проект на модерацию в текущем статусе.")
    return redirect("frontend:project_detail", pk=project.pk)


# ---------------------------------------------------------------------------
# Project Delete
# ---------------------------------------------------------------------------

@require_POST
@login_required(login_url="/auth/")
def project_delete(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)

    if project.owner != request.user and not request.user.is_staff:
        raise Http404

    if project.status not in _DELETABLE_STATUSES:
        messages.error(request, f"Нельзя удалить проект со статусом «{project.get_status_display()}».")
        return redirect("frontend:project_detail", pk=project.pk)

    title = project.title
    project.delete()
    messages.success(request, f"Проект «{title}» удалён.")
    return redirect("frontend:project_list")
