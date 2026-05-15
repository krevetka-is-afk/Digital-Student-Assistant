from apps.frontend.decorators import moderator_required
from apps.frontend.forms import ExternalAllowlistBulkForm
from apps.frontend.utils import LOGIN_URL, flash_form_errors
from apps.users.models import (
    ExternalAccessAllowlist,
    ExternalAccessRequest,
    ExternalAccessRequestStatus,
)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .dashboard import _cpprp_tab_redirect


@login_required(login_url=LOGIN_URL)
@moderator_required
@require_POST
def cpprp_external_allowlist_bulk_add(request):
    form = ExternalAllowlistBulkForm(request.POST)
    if not form.is_valid():
        flash_form_errors(request, form)
        return _cpprp_tab_redirect("external-access")

    cleaned       = form.cleaned_data
    created_count = 0
    updated_count = 0
    for email in cleaned["emails"]:
        entry, created = ExternalAccessAllowlist.objects.get_or_create(
            email=email,
            defaults={
                "allowed_role": cleaned["allowed_role"],
                "note":         cleaned["note"],
                "approved_by":  request.user,
                "is_active":    True,
            },
        )
        if created:
            created_count += 1
            continue
        entry.allowed_role = cleaned["allowed_role"]
        entry.note         = cleaned["note"]
        entry.approved_by  = request.user
        entry.is_active    = True
        entry.save(update_fields=["allowed_role", "note", "approved_by", "is_active", "updated_at"])
        updated_count += 1

    messages.success(
        request,
        f"External allowlist updated: created {created_count}, updated {updated_count}.",
    )
    return _cpprp_tab_redirect("external-access")

@login_required(login_url=LOGIN_URL)
@moderator_required
@require_POST
def cpprp_external_request_approve(request, pk):
    access_request = get_object_or_404(ExternalAccessRequest, pk=pk)
    with transaction.atomic():
        entry, _ = ExternalAccessAllowlist.objects.get_or_create(
            email=access_request.email,
            defaults={
                "allowed_role": access_request.requested_role,
                "approved_by":  request.user,
                "note":         "Approved from external access request.",
                "is_active":    True,
            },
        )
        entry.allowed_role = access_request.requested_role
        entry.approved_by  = request.user
        entry.is_active    = True
        if not entry.note:
            entry.note = "Approved from external access request."
        entry.save(update_fields=["allowed_role", "approved_by", "is_active", "note", "updated_at"])

        access_request.status        = ExternalAccessRequestStatus.APPROVED
        access_request.reviewed_by   = request.user
        access_request.reviewed_at   = timezone.now()
        access_request.decision_note = "Approved and added to allowlist."
        access_request.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "decision_note", "updated_at"]
        )
    messages.success(request, f"{access_request.email} approved and added to allowlist.")
    return _cpprp_tab_redirect("external-access")

@login_required(login_url=LOGIN_URL)
@moderator_required
@require_POST
def cpprp_external_request_reject(request, pk):
    access_request = get_object_or_404(ExternalAccessRequest, pk=pk)
    access_request.status        = ExternalAccessRequestStatus.REJECTED
    access_request.reviewed_by   = request.user
    access_request.reviewed_at   = timezone.now()
    access_request.decision_note = "Rejected by moderator."
    access_request.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "decision_note", "updated_at"]
    )
    messages.success(request, f"{access_request.email} rejected.")
    return _cpprp_tab_redirect("external-access")

@login_required(login_url=LOGIN_URL)
@moderator_required
@require_POST
def cpprp_external_allowlist_toggle(request, pk):
    entry            = get_object_or_404(ExternalAccessAllowlist, pk=pk)
    entry.is_active  = not entry.is_active
    entry.approved_by = request.user
    entry.save(update_fields=["is_active", "approved_by", "updated_at"])
    state = "activated" if entry.is_active else "deactivated"
    messages.success(request, f"{entry.email} {state}.")
    return _cpprp_tab_redirect("external-access")
