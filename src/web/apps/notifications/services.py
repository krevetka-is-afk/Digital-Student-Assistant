from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Notification, NotificationEmailStatus

User = get_user_model()


@dataclass(frozen=True, slots=True)
class NotificationSpec:
    event_type: str
    title: str
    body: str
    target_type: str
    target_id: str
    actor_id: int | None = None
    dedupe_key: str | None = None


def _normalize_recipients(recipients: Iterable[object]) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for item in recipients:
        if item is None:
            continue
        raw_id = getattr(item, "id", None) if not isinstance(item, int) else item
        if raw_id is None:
            continue
        recipient_id = int(raw_id)
        if recipient_id in seen:
            continue
        seen.add(recipient_id)
        ids.append(recipient_id)
    return ids


def _should_send_email(user) -> bool:
    email = (getattr(user, "email", "") or "").strip()
    if not email:
        return False
    try:
        profile = user.profile
    except Exception:
        return True
    return bool(getattr(profile, "email_verified_at", None))


def _email_subject(notification: Notification) -> str:
    if notification.event_type == "messaging.new_message":
        return "DSA: У вас новые сообщения"
    return f"DSA: {notification.title}"


def _email_body(notification: Notification) -> str:
    if notification.body:
        return notification.body
    return notification.title


_EVENT_TEMPLATE_MAP: dict[str, str] = {
    "application.review.accepted": "notifications/email/application_approved.html",
    "initiative.moderation.approved": "notifications/email/application_approved.html",
    "project.moderation.approved": "notifications/email/application_approved.html",
    "application.review.rejected": "notifications/email/application_rejected.html",
    "initiative.moderation.rejected": "notifications/email/application_rejected.html",
    "project.moderation.rejected": "notifications/email/application_rejected.html",
    "messaging.new_message": "notifications/email/message_received.html",
}


def _template_for_notification(notification: Notification) -> str:
    return _EVENT_TEMPLATE_MAP.get(notification.event_type, "notifications/email/notification.html")


def _send_email_for_notification(notification_id: int) -> None:
    notification = (
        Notification.objects.select_related("recipient").filter(pk=notification_id).first()
    )
    if notification is None:
        return
    user = notification.recipient
    if not _should_send_email(user):
        notification.email_status = NotificationEmailStatus.SKIPPED
        notification.email_sent_at = timezone.now()
        notification.email_error = ""
        notification.save(update_fields=["email_status", "email_sent_at", "email_error"])
        return

    # Digest deduplication: for messaging notifications send at most one email
    # per recipient per calendar day. Subsequent messages arrive as in-app
    # notifications (visible via SSE) but do not trigger additional emails.
    if notification.event_type == "messaging.new_message":
        today = timezone.now().date()
        already_sent_today = (
            Notification.objects
            .filter(
                recipient_id=notification.recipient_id,
                event_type="messaging.new_message",
                email_status=NotificationEmailStatus.SENT,
                email_sent_at__date=today,
            )
            .exclude(pk=notification.pk)
            .exists()
        )
        if already_sent_today:
            notification.email_status = NotificationEmailStatus.SKIPPED
            notification.email_sent_at = timezone.now()
            notification.email_error = ""
            notification.save(update_fields=["email_status", "email_sent_at", "email_error"])
            return

    try:
        site_url = getattr(settings, "SITE_URL", "").rstrip("/")
        html_body = render_to_string(
            _template_for_notification(notification),
            {"notification": notification, "site_url": site_url},
        )
        plain_body = _email_body(notification)
        msg = EmailMultiAlternatives(
            subject=_email_subject(notification),
            body=plain_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@localhost"),
            to=[user.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()
    except Exception as exc:
        notification.email_status = NotificationEmailStatus.FAILED
        notification.email_sent_at = timezone.now()
        notification.email_error = str(exc)
        notification.save(update_fields=["email_status", "email_sent_at", "email_error"])
        return

    notification.email_status = NotificationEmailStatus.SENT
    notification.email_sent_at = timezone.now()
    notification.email_error = ""
    notification.save(update_fields=["email_status", "email_sent_at", "email_error"])


def create_notifications(
    *, recipients: Iterable[object], spec: NotificationSpec
) -> list[Notification]:
    recipient_ids = _normalize_recipients(recipients)
    if not recipient_ids:
        return []

    notifications: list[Notification] = []
    for recipient_id in recipient_ids:
        try:
            with transaction.atomic():
                notification = Notification.objects.create(
                    recipient_id=recipient_id,
                    actor_id=spec.actor_id,
                    event_type=spec.event_type,
                    title=spec.title,
                    body=spec.body,
                    target_type=spec.target_type,
                    target_id=str(spec.target_id),
                    dedupe_key=spec.dedupe_key,
                    email_status=NotificationEmailStatus.PENDING,
                )
        except IntegrityError:
            if spec.dedupe_key:
                existing = Notification.objects.filter(dedupe_key=spec.dedupe_key).first()
                if existing is not None:
                    notifications.append(existing)
            continue
        notifications.append(notification)

        transaction.on_commit(lambda nid=notification.pk: _send_email_for_notification(nid))

    return notifications
