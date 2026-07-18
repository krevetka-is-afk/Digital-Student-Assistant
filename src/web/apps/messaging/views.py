from __future__ import annotations

from apps.notifications.services import NotificationSpec, create_notifications
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render

from .models import Message, Thread

User = get_user_model()

MAX_BODY_LENGTH = 5000


@login_required
def thread_list(request):
    return render(
        request,
        "messaging/thread_list.html",
        {"threads_with_meta": _thread_list_ctx(request.user)},
    )


def _thread_list_ctx(user):
    threads = (
        Thread.objects.filter(participants=user)
        .annotate(
            unread_count=Count(
                "messages",
                filter=~Q(messages__sender=user) & ~Q(messages__read_by=user),
                distinct=True,
            )
        )
        .prefetch_related(
            "participants",
            Prefetch(
                "messages",
                queryset=Message.objects.order_by("-created_at"),
            ),
        )
        .order_by("-updated_at")
    )
    result = []
    for t in threads:
        others = [p for p in t.participants.all() if p.pk != user.pk]
        result.append((t, t.unread_count, others))
    return result


def _mark_thread_read(thread, user) -> None:
    unread_ids = list(
        thread.messages
        .exclude(sender=user)
        .exclude(read_by=user)
        .values_list("id", flat=True)
    )
    if unread_ids:
        Through = Message.read_by.through
        Through.objects.bulk_create(
            [Through(message_id=mid, user_id=user.pk) for mid in unread_ids],
            ignore_conflicts=True,
        )


@login_required
def thread_detail(request, pk):
    thread = get_object_or_404(Thread, pk=pk, participants=request.user)
    messages_qs = thread.messages.select_related("sender").all()

    _mark_thread_read(thread, request.user)

    errors = {}
    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        if not body:
            errors["body"] = "Введите текст сообщения."
        elif len(body) > MAX_BODY_LENGTH:
            errors["body"] = f"Сообщение не должно превышать {MAX_BODY_LENGTH} символов."

        if not errors:
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

    other_participants = [p for p in thread.participants.all() if p.pk != request.user.pk]
    return render(
        request,
        "messaging/thread_detail.html",
        {
            "thread": thread,
            "chat_messages": messages_qs,
            "other_participants": other_participants,
            "threads_with_meta": _thread_list_ctx(request.user),
            "errors": errors,
            "post": request.POST if request.method == "POST" else {},
        },
    )


@login_required
def thread_messages_partial(request, pk):
    """HTMX polling endpoint — returns only the messages list fragment."""
    thread = get_object_or_404(Thread, pk=pk, participants=request.user)
    _mark_thread_read(thread, request.user)
    messages_qs = thread.messages.select_related("sender").all()
    return render(
        request,
        "messaging/partials/thread_messages.html",
        {"thread": thread, "chat_messages": messages_qs},
    )


@login_required
def thread_open(request):
    raw_to = request.GET.get("to", "").strip()
    if not raw_to.isdigit():
        return redirect("messaging:thread_list")

    other = get_object_or_404(User, pk=int(raw_to))
    if other == request.user:
        return redirect("messaging:thread_list")

    thread = (
        Thread.objects.filter(participants=request.user)
        .filter(participants=other)
        .order_by("-updated_at")
        .first()
    )

    if thread is None:
        subject = request.GET.get("subject", "").strip()
        if not subject:
            name = other.get_full_name() or other.username
            subject = f"Диалог с {name}"
        thread = Thread.objects.create(subject=subject)
        thread.participants.add(request.user, other)

    return redirect("messaging:thread_detail", pk=thread.pk)


@login_required
def thread_create(request):
    users = User.objects.exclude(pk=request.user.pk).order_by("username")
    errors = {}

    raw_to = request.GET.get("to", "").strip()
    preset_subject = request.GET.get("subject", "").strip()
    preselected_id = int(raw_to) if raw_to.isdigit() else None
    preselected_user = None
    if preselected_id:
        preselected_user = User.objects.filter(pk=preselected_id).first()

    if request.method == "POST":
        recipient_id = request.POST.get("recipient", "").strip()
        body = request.POST.get("body", "").strip()

        if not recipient_id:
            errors["recipient"] = "Выберите получателя."
        elif recipient_id.isdigit() and int(recipient_id) == request.user.pk:
            errors["recipient"] = "Нельзя отправить сообщение самому себе."

        if not body:
            errors["body"] = "Введите текст сообщения."
        elif len(body) > MAX_BODY_LENGTH:
            errors["body"] = f"Сообщение не должно превышать {MAX_BODY_LENGTH} символов."

        if not errors:
            recipient = get_object_or_404(User, pk=recipient_id)

            existing = (
                Thread.objects.filter(participants=request.user)
                .filter(participants=recipient)
                .order_by("-updated_at")
                .first()
            )
            if existing:
                Message.objects.create(thread=existing, sender=request.user, body=body)
                existing.save()
                create_notifications(
                    recipients=[recipient],
                    spec=NotificationSpec(
                        event_type="messaging.new_message",
                        title=f"Новое сообщение в «{existing.subject}»",
                        body=body[:120],
                        target_type="thread",
                        target_id=str(existing.pk),
                        actor_id=request.user.pk,
                    ),
                )
                return redirect("messaging:thread_detail", pk=existing.pk)

            subject = request.POST.get("subject", "").strip()
            if not subject:
                name = recipient.get_full_name() or recipient.username
                subject = f"Диалог с {name}"
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

        if "recipient" not in errors:
            preselected_id = int(recipient_id) if recipient_id.isdigit() else None
            preselected_user = User.objects.filter(pk=preselected_id).first() if preselected_id else None
        else:
            preselected_id = None
            preselected_user = None

    return render(request, "messaging/thread_create.html", {
        "users": users,
        "errors": errors,
        "post": request.POST if request.method == "POST" else {},
        "preselected_id": preselected_id,
        "preselected_user": preselected_user,
        "preset_subject": preset_subject,
    })
