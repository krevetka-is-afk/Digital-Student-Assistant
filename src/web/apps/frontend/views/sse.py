from __future__ import annotations

import json
import time

from apps.notifications.models import Notification
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse


@login_required
def notification_stream(request):
    def event_stream():
        try:
            last_id = int(request.GET.get("lastId") or 0)
        except (ValueError, TypeError):
            last_id = 0

        unread_count = Notification.objects.filter(
            recipient=request.user, read_at__isnull=True
        ).count()
        yield f"data: {json.dumps({'type': 'init', 'unread_count': unread_count})}\n\n"

        for _ in range(60):
            new_items = list(
                Notification.objects.filter(recipient=request.user, id__gt=last_id).order_by("id")[
                    :5
                ]
            )
            if new_items:
                for n in new_items:
                    last_id = n.pk
                    payload = {
                        "type": "notification",
                        "id": n.pk,
                        "title": n.title,
                        "body": n.body,
                        "event_type": n.event_type,
                        "read": n.read_at is not None,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
            else:
                yield ": heartbeat\n\n"
            time.sleep(3)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
