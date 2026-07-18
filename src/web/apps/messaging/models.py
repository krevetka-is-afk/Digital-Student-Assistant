from __future__ import annotations

from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class Thread(models.Model):
    subject = models.CharField(max_length=255)
    participants = models.ManyToManyField(User, related_name="message_threads")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.subject

    def last_message(self):
        cache = getattr(self, "_prefetched_objects_cache", {})
        if "messages" in cache:
            msgs = cache["messages"]
            return msgs[0] if msgs else None
        return self.messages.order_by("-created_at").first()

    def unread_count_for(self, user) -> int:
        return self.messages.exclude(sender=user).exclude(read_by=user).count()


class Message(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_by = models.ManyToManyField(User, related_name="read_messages", blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Message from {self.sender_id} in thread {self.thread_id}"
