from __future__ import annotations

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

    if request.method == "POST":
        recipient_id = request.POST.get("recipient")
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()

        if recipient_id and subject and body:
            recipient = get_object_or_404(User, pk=recipient_id)
            thread = Thread.objects.create(subject=subject)
            thread.participants.add(request.user, recipient)
            Message.objects.create(thread=thread, sender=request.user, body=body)
            return redirect("messaging:thread_detail", pk=thread.pk)

    return render(request, "messaging/thread_create.html", {"users": users})
