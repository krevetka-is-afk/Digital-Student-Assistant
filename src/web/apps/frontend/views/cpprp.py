"""
CPPRP administration dashboard.

Provides a unified tabbed interface for:
  - Overview (stats across the whole platform)
  - All applications (paginated, filterable)
  - Platform deadlines (CRUD)
  - Document templates (CRUD)
  - CSV and XLSX exports
"""

import csv
import logging
import re

from apps.account.models import DeadlineAudience, DocumentTemplate, PlatformDeadline
from apps.applications.models import Application, ApplicationStatus
from apps.frontend.decorators import moderator_required
from apps.projects.export_epp_xlsx import LegacyVariant, build_projects_xlsx_bytes
from apps.projects.models import Project, ProjectStatus
from apps.users.models import (
    ExternalAccessAllowlist,
    ExternalAccessRequest,
    ExternalAccessRequestStatus,
    UserRole,
    normalize_email,
)
from django import forms as dj_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

_APPS_PAGE_SIZE = 20
_EXTERNAL_EMAIL_SPLIT_RE = re.compile(r"[\s,;]+")


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

class DeadlineForm(dj_forms.Form):
    slug = dj_forms.SlugField(
        max_length=80,
        error_messages={"required": "Введите slug (латиница, цифры, дефис)."},
    )
    title = dj_forms.CharField(
        max_length=255,
        error_messages={"required": "Название обязательно."},
    )
    audience = dj_forms.ChoiceField(
        choices=DeadlineAudience.choices,
    )
    description = dj_forms.CharField(widget=dj_forms.Textarea, required=False)
    starts_at = dj_forms.DateTimeField(
        required=False,
        widget=dj_forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    ends_at = dj_forms.DateTimeField(
        required=False,
        widget=dj_forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    is_active = dj_forms.BooleanField(required=False, initial=True)


class TemplateForm(dj_forms.Form):
    slug = dj_forms.SlugField(
        max_length=80,
        error_messages={"required": "Введите slug."},
    )
    title = dj_forms.CharField(
        max_length=255,
        error_messages={"required": "Название обязательно."},
    )
    url = dj_forms.URLField(
        error_messages={"required": "URL обязателен.", "invalid": "Введите корректный URL."},
    )
    audience = dj_forms.ChoiceField(
        choices=DeadlineAudience.choices,
    )
    description = dj_forms.CharField(widget=dj_forms.Textarea, required=False)
    is_active = dj_forms.BooleanField(required=False, initial=True)


class ExternalAllowlistBulkForm(dj_forms.Form):
    emails = dj_forms.CharField(
        widget=dj_forms.Textarea,
        error_messages={"required": "Укажите хотя бы один email."},
    )
    allowed_role = dj_forms.ChoiceField(
        choices=[(UserRole.CUSTOMER, "Customer")],
        initial=UserRole.CUSTOMER,
    )
    note = dj_forms.CharField(required=False, max_length=255)


def _extract_external_email_list(raw: str) -> list[str]:
    values = []
    seen: set[str] = set()
    for part in _EXTERNAL_EMAIL_SPLIT_RE.split(raw or ""):
        email = normalize_email(part)
        if not email or email in seen:
            continue
        seen.add(email)
        values.append(email)
    return values


# ---------------------------------------------------------------------------
# Dashboard (main view)
# ---------------------------------------------------------------------------

@login_required(login_url="/auth/")
@moderator_required
def cpprp_dashboard(request):
    """CPPRP administration hub — tabbed page."""
    # ── Stats ────────────────────────────────────────────────────────────────
    project_counts = {
        s: Project.objects.filter(status=s).count()
        for s in [
            ProjectStatus.PUBLISHED,
            ProjectStatus.ON_MODERATION,
            ProjectStatus.STAFFED,
            ProjectStatus.DRAFT,
        ]
    }
    app_totals = {
        "submitted": Application.objects.filter(status=ApplicationStatus.SUBMITTED).count(),
        "accepted": Application.objects.filter(status=ApplicationStatus.ACCEPTED).count(),
        "rejected": Application.objects.filter(status=ApplicationStatus.REJECTED).count(),
    }
    app_totals["total"] = sum(app_totals.values())

    # ── Applications tab ─────────────────────────────────────────────────────
    app_status_filter = request.GET.get("status", "").strip()
    app_page = request.GET.get("page", 1)

    apps_qs = (
        Application.objects.select_related("applicant", "project")
        .order_by("-created_at")
    )
    if app_status_filter and app_status_filter in ApplicationStatus.values:
        apps_qs = apps_qs.filter(status=app_status_filter)

    apps_paginator = Paginator(apps_qs, _APPS_PAGE_SIZE)
    apps_page_obj = apps_paginator.get_page(app_page)

    # ── Deadlines tab ────────────────────────────────────────────────────────
    deadlines = list(PlatformDeadline.objects.order_by("ends_at", "title"))
    deadline_form = DeadlineForm()

    # ── Templates tab ────────────────────────────────────────────────────────
    templates = list(DocumentTemplate.objects.order_by("title"))
    template_form = TemplateForm()
    external_pending_requests = list(
        ExternalAccessRequest.objects.filter(status=ExternalAccessRequestStatus.PENDING)
        .order_by("created_at")
    )
    external_recent_requests = list(
        ExternalAccessRequest.objects.select_related("reviewed_by").order_by("-updated_at")[:20]
    )
    external_allowlist = list(
        ExternalAccessAllowlist.objects.select_related("approved_by").order_by("email")[:50]
    )
    external_allowlist_form = ExternalAllowlistBulkForm()

    context = {
        "project_counts": project_counts,
        "app_totals": app_totals,
        "apps_page_obj": apps_page_obj,
        "app_status_filter": app_status_filter,
        "deadlines": deadlines,
        "deadline_form": deadline_form,
        "templates": templates,
        "template_form": template_form,
        "external_pending_requests": external_pending_requests,
        "external_recent_requests": external_recent_requests,
        "external_allowlist": external_allowlist,
        "external_allowlist_form": external_allowlist_form,
        "ApplicationStatus": ApplicationStatus,
        "ProjectStatus": ProjectStatus,
        "DeadlineAudience": DeadlineAudience,
        "ExternalAccessRequestStatus": ExternalAccessRequestStatus,
    }
    return render(request, "frontend/cpprp_dashboard.html", context)


# ---------------------------------------------------------------------------
# Deadlines CRUD
# ---------------------------------------------------------------------------

@require_POST
@login_required(login_url="/auth/")
@moderator_required
def cpprp_deadline_create(request):
    form = DeadlineForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            PlatformDeadline.objects.create(
                slug=d["slug"],
                title=d["title"],
                audience=d["audience"],
                description=d.get("description", ""),
                starts_at=d.get("starts_at"),
                ends_at=d.get("ends_at"),
                is_active=d.get("is_active", True),
            )
            messages.success(request, f"Дедлайн «{d['title']}» создан.")
        except Exception:
            messages.error(request, "Не удалось создать дедлайн (возможно, slug уже занят).")
    else:
        for field, errs in form.errors.items():
            messages.error(request, f"{field}: {errs[0]}")
    return redirect("/cpprp/?tab=deadlines")


@require_POST
@login_required(login_url="/auth/")
@moderator_required
def cpprp_deadline_toggle(request, pk):
    dl = get_object_or_404(PlatformDeadline, pk=pk)
    dl.is_active = not dl.is_active
    dl.save(update_fields=["is_active", "updated_at"])
    state = "активирован" if dl.is_active else "деактивирован"
    messages.success(request, f"Дедлайн «{dl.title}» {state}.")
    return redirect("/cpprp/?tab=deadlines")


@require_POST
@login_required(login_url="/auth/")
@moderator_required
def cpprp_deadline_delete(request, pk):
    dl = get_object_or_404(PlatformDeadline, pk=pk)
    title = dl.title
    dl.delete()
    messages.success(request, f"Дедлайн «{title}» удалён.")
    return redirect("/cpprp/?tab=deadlines")


# ---------------------------------------------------------------------------
# Templates CRUD
# ---------------------------------------------------------------------------

@require_POST
@login_required(login_url="/auth/")
@moderator_required
def cpprp_template_create(request):
    form = TemplateForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            DocumentTemplate.objects.create(
                slug=d["slug"],
                title=d["title"],
                url=d["url"],
                audience=d["audience"],
                description=d.get("description", ""),
                is_active=d.get("is_active", True),
            )
            messages.success(request, f"Шаблон «{d['title']}» добавлен.")
        except Exception:
            messages.error(request, "Не удалось добавить шаблон (возможно, slug уже занят).")
    else:
        for field, errs in form.errors.items():
            messages.error(request, f"{field}: {errs[0]}")
    return redirect("/cpprp/?tab=templates")


@require_POST
@login_required(login_url="/auth/")
@moderator_required
def cpprp_template_toggle(request, pk):
    tpl = get_object_or_404(DocumentTemplate, pk=pk)
    tpl.is_active = not tpl.is_active
    tpl.save(update_fields=["is_active", "updated_at"])
    state = "активирован" if tpl.is_active else "деактивирован"
    messages.success(request, f"Шаблон «{tpl.title}» {state}.")
    return redirect("/cpprp/?tab=templates")


@require_POST
@login_required(login_url="/auth/")
@moderator_required
def cpprp_template_delete(request, pk):
    tpl = get_object_or_404(DocumentTemplate, pk=pk)
    title = tpl.title
    tpl.delete()
    messages.success(request, f"Шаблон «{title}» удалён.")
    return redirect("/cpprp/?tab=templates")


# ---------------------------------------------------------------------------
# CSV / XLSX Exports
# ---------------------------------------------------------------------------

@login_required(login_url="/auth/")
@moderator_required
def cpprp_export_projects_xlsx(request):
    """Download projects as XLSX (EPP-compatible sheet + optional extended sheet)."""
    variant_raw = (request.GET.get("variant") or "both").lower()
    variant: LegacyVariant = (
        variant_raw if variant_raw in ("compatible", "extended", "both") else "both"
    )
    payload = build_projects_xlsx_bytes(Project.objects.all(), variant=variant)
    response = HttpResponse(
        payload,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="projects-export-{variant}.xlsx"'
    return response


@login_required(login_url="/auth/")
@moderator_required
def cpprp_export_projects(request):
    """Download all projects as CSV."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="projects-export.csv"'
    response.write("﻿")  # BOM for Excel UTF-8 compatibility

    writer = csv.writer(response)
    writer.writerow([
        "id", "title", "status", "source_type",
        "team_size", "accepted_participants_count",
        "education_program", "study_course", "created_at",
    ])
    for p in Project.objects.select_related("owner").order_by("pk"):
        writer.writerow([
            p.pk, p.title, p.status, p.source_type,
            p.team_size, p.accepted_participants_count,
            p.education_program, p.study_course,
            p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
        ])
    return response


@login_required(login_url="/auth/")
@moderator_required
def cpprp_export_applications(request):
    """Download all applications as CSV."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="applications-export.csv"'
    response.write("﻿")  # BOM for Excel UTF-8 compatibility

    writer = csv.writer(response)
    writer.writerow([
        "id", "project_id", "project_title",
        "applicant_id", "applicant_email",
        "status", "created_at",
    ])
    for a in Application.objects.select_related("project", "applicant").order_by("pk"):
        writer.writerow([
            a.pk, a.project_id, a.project.title,
            a.applicant_id, a.applicant.email,
            a.status,
            a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
        ])
    return response


@require_POST
@login_required(login_url="/auth/")
@moderator_required
def cpprp_external_allowlist_bulk_add(request):
    form = ExternalAllowlistBulkForm(request.POST)
    if not form.is_valid():
        for field, errs in form.errors.items():
            messages.error(request, f"{field}: {errs[0]}")
        return redirect("/cpprp/?tab=external-access")

    cleaned = form.cleaned_data
    emails = _extract_external_email_list(cleaned["emails"])
    if not emails:
        messages.error(request, "Не удалось извлечь ни одного корректного email.")
        return redirect("/cpprp/?tab=external-access")

    created_count = 0
    updated_count = 0
    for email in emails:
        entry, created = ExternalAccessAllowlist.objects.get_or_create(
            email=email,
            defaults={
                "allowed_role": cleaned["allowed_role"],
                "note": cleaned.get("note", ""),
                "approved_by": request.user,
                "is_active": True,
            },
        )
        if created:
            created_count += 1
            continue
        entry.allowed_role = cleaned["allowed_role"]
        entry.note = cleaned.get("note", "")
        entry.approved_by = request.user
        entry.is_active = True
        entry.save(update_fields=["allowed_role", "note", "approved_by", "is_active", "updated_at"])
        updated_count += 1

    messages.success(
        request,
        f"Список внешних почт обновлён: создано {created_count}, обновлено {updated_count}.",
    )
    return redirect("/cpprp/?tab=external-access")


@require_POST
@login_required(login_url="/auth/")
@moderator_required
def cpprp_external_request_approve(request, pk):
    access_request = get_object_or_404(ExternalAccessRequest, pk=pk)
    entry, _ = ExternalAccessAllowlist.objects.get_or_create(
        email=access_request.email,
        defaults={
            "allowed_role": access_request.requested_role,
            "approved_by": request.user,
            "note": "Approved from external access request.",
            "is_active": True,
        },
    )
    entry.allowed_role = access_request.requested_role
    entry.approved_by = request.user
    entry.is_active = True
    if not entry.note:
        entry.note = "Approved from external access request."
    entry.save(update_fields=["allowed_role", "approved_by", "is_active", "note", "updated_at"])

    access_request.status = ExternalAccessRequestStatus.APPROVED
    access_request.reviewed_by = request.user
    access_request.reviewed_at = timezone.now()
    access_request.decision_note = "Approved and added to allowlist."
    access_request.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "decision_note", "updated_at"]
    )
    messages.success(
        request,
        f"Почта {access_request.email} одобрена и добавлена в allowlist.",
    )
    return redirect("/cpprp/?tab=external-access")


@require_POST
@login_required(login_url="/auth/")
@moderator_required
def cpprp_external_request_reject(request, pk):
    access_request = get_object_or_404(ExternalAccessRequest, pk=pk)
    access_request.status = ExternalAccessRequestStatus.REJECTED
    access_request.reviewed_by = request.user
    access_request.reviewed_at = timezone.now()
    access_request.decision_note = "Rejected by moderator."
    access_request.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "decision_note", "updated_at"]
    )
    messages.success(request, f"Заявка {access_request.email} отклонена.")
    return redirect("/cpprp/?tab=external-access")


@require_POST
@login_required(login_url="/auth/")
@moderator_required
def cpprp_external_allowlist_toggle(request, pk):
    entry = get_object_or_404(ExternalAccessAllowlist, pk=pk)
    entry.is_active = not entry.is_active
    entry.approved_by = request.user
    entry.save(update_fields=["is_active", "approved_by", "updated_at"])
    state = "активирована" if entry.is_active else "деактивирована"
    messages.success(request, f"Внешняя почта {entry.email} {state}.")
    return redirect("/cpprp/?tab=external-access")
