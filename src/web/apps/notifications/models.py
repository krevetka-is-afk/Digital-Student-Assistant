from __future__ import annotations

from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class NotificationEmailStatus(models.TextChoices):
    SKIPPED = "skipped", "Skipped"
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class Notification(models.Model):
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="notifications_acted",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=120, db_index=True)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    target_type = models.CharField(max_length=50, db_index=True)
    target_id = models.CharField(max_length=100, db_index=True)
    dedupe_key = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Optional idempotency key to avoid duplicates for retried actions.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)

    email_status = models.CharField(
        max_length=20,
        choices=NotificationEmailStatus.choices,
        default=NotificationEmailStatus.PENDING,
        db_index=True,
    )
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_error = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["recipient", "created_at"], name="notif_recipient_time_idx"),
            models.Index(fields=["recipient", "read_at"], name="notif_recipient_read_idx"),
            models.Index(fields=["target_type", "target_id"], name="notif_target_idx"),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.target_type}:{self.target_id} -> {self.recipient_id}"
