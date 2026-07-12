from __future__ import annotations

from apps.notifications.models import Notification
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST


@login_required
def notifications_page(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:50]
    return render(request, "frontend/notifications.html", {"notifications": notifications})


@login_required
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return JsonResponse({"ok": True})
