from __future__ import annotations


def unread_messages_count(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"unread_messages_count": 0}
    from .models import Message

    count = (
        Message.objects.filter(thread__participants=request.user)
        .exclude(sender=request.user)
        .exclude(read_by=request.user)
        .count()
    )
    return {"unread_messages_count": count}
