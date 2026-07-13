from __future__ import annotations

from apps.notifications.services import NotificationSpec, create_notifications
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Message, Thread

User = get_user_model()


@login_required
def thread_list(request):
    threads = (
        Thread.objects.filter(participants=request.user)
        .prefetch_related("participants", "messages")
        .order_by("-updated_at")
    )
    threads_with_unread = [(t, t.unread_count_for(request.user)) for t in threads]
    return render(
        request,
        "messaging/thread_list.html",
        {
            "threads_with_unread": threads_with_unread,
        },
    )


@login_required
def thread_detail(request, pk):
    thread = get_object_or_404(Thread, pk=pk, participants=request.user)
    messages_qs = thread.messages.select_related("sender").all()

    for msg in messages_qs:
        if request.user not in msg.read_by.all():
            msg.read_by.add(request.user)

    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        if body:
            Message.objects.create(thread=thread, sender=request.user, body=body)
            thread.save()
            other_participants = thread.participants.exclude(pk=request.user.pk)
            create_notifications(
                recipients=list(other_participants),
                spec=NotificationSpec(
                    event_type="messaging.new_message",
                    title=f"Новое сообщение в «{thread.subject}»",
                    body=body[:120],
                    target_type="thread",
                    target_id=str(thread.pk),
                    actor_id=request.user.pk,
                ),
            )
            return redirect("messaging:thread_detail", pk=pk)

    return render(
        request,
        "messaging/thread_detail.html",
        {
            "thread": thread,
            "messages": messages_qs,
        },
    )


@login_required
def thread_create(request):
    users = User.objects.exclude(pk=request.user.pk).order_by("username")
    preselected_id = request.GET.get("to")
    errors = {}

    if request.method == "POST":
        recipient_id = request.POST.get("recipient", "").strip()
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()
        preselected_id = recipient_id

        if not recipient_id:
            errors["recipient"] = "Выберите получателя."
        if not subject:
            errors["subject"] = "Укажите тему сообщения."
        if not body:
            errors["body"] = "Введите текст сообщения."

        if not errors:
            recipient = get_object_or_404(User, pk=recipient_id)
            thread = Thread.objects.create(subject=subject)
            thread.participants.add(request.user, recipient)
            Message.objects.create(thread=thread, sender=request.user, body=body)
            create_notifications(
                recipients=[recipient],
                spec=NotificationSpec(
                    event_type="messaging.new_message",
                    title=f"Новое сообщение: «{subject}»",
                    body=body[:120],
                    target_type="thread",
                    target_id=str(thread.pk),
                    actor_id=request.user.pk,
                ),
            )
            return redirect("messaging:thread_detail", pk=thread.pk)

    return render(request, "messaging/thread_create.html", {
        "users": users,
        "errors": errors,
        "post": request.POST if request.method == "POST" else {},
        "preselected_id": int(preselected_id) if preselected_id and preselected_id.isdigit() else None,
    })
