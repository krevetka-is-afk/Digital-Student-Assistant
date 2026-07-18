from __future__ import annotations

import json
import time

from apps.notifications.models import Notification
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse


@login_required
def notification_stream(request):
    def event_stream():
        # Prefer the standard SSE reconnect header; fall back to query param.
        # The browser sends Last-Event-ID automatically after seeing id: fields.
        raw_header = request.META.get("HTTP_LAST_EVENT_ID", "").strip()
        try:
            last_id = int(raw_header) if raw_header else int(request.GET.get("lastId") or 0)
        except (ValueError, TypeError):
            last_id = 0

        # Clamp: any value <= 0 is treated as a fresh connect to avoid
        # flooding all existing notifications as toasts on reconnect.
        if last_id <= 0:
            latest = (
                Notification.objects
                .filter(recipient=request.user)
                .order_by("-id")
                .values_list("id", flat=True)
                .first()
            )
            if latest:
                last_id = latest

        unread_count = Notification.objects.filter(
            recipient=request.user, read_at__isnull=True
        ).count()
        # retry: tells the browser to wait 3 s before auto-reconnecting.
        yield "retry: 3000\n"
        yield f"data: {json.dumps({'type': 'init', 'unread_count': unread_count})}\n\n"

        for _ in range(60):
            try:
                new_items = list(
                    Notification.objects
                    .filter(recipient=request.user, id__gt=last_id)
                    .order_by("id")[:5]
                )
                if new_items:
                    for n in new_items:
                        last_id = n.pk
                    unread_count = Notification.objects.filter(
                        recipient=request.user, read_at__isnull=True
                    ).count()
                    for n in new_items:
                        payload = {
                            "type": "notification",
                            "id": n.pk,
                            "title": n.title,
                            "body": n.body,
                            "event_type": n.event_type,
                            "read": n.read_at is not None,
                            "unread_count": unread_count,
                        }
                        yield (
                            f"id: {n.pk}\n"
                            f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        )
                else:
                    yield ": heartbeat\n\n"
            except Exception:
                # DB hiccup — keep the stream alive with a heartbeat.
                yield ": heartbeat\n\n"
            time.sleep(3)

    response = StreamingHttpResponse(
        event_stream(), content_type="text/event-stream; charset=utf-8"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
