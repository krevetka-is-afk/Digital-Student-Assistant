from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from apps.notifications.models import Notification, NotificationEmailStatus
from apps.notifications.services import (
    NotificationSpec,
    _email_subject,
    _send_email_for_notification,
    _should_send_email,
    _template_for_notification,
    create_notifications,
)
from apps.users.models import UserProfile, UserRole

User = get_user_model()

pytestmark = pytest.mark.django_db


def _uid():
    return uuid4().hex[:8]


def _make_user(email=None):
    username = f"user-{_uid()}"
    return User.objects.create_user(
        username=username,
        email=email or f"{username}@test.com",
        password="pass",
    )


def _make_verified_user():
    user = _make_user()
    profile = UserProfile.objects.create(user=user, role=UserRole.STUDENT)
    profile.mark_email_verified()
    profile.save()
    return user


def _make_unverified_user():
    user = _make_user()
    UserProfile.objects.create(user=user, role=UserRole.STUDENT)
    return user


def _make_notification(user, event_type="test.event", title="Тест", body="Тело"):
    return Notification.objects.create(
        recipient=user,
        event_type=event_type,
        title=title,
        body=body,
        target_type="test",
        target_id="1",
        email_status=NotificationEmailStatus.PENDING,
    )


def test_should_send_email_true_for_verified_user():
    user = _make_verified_user()
    assert _should_send_email(user) is True


def test_should_send_email_false_for_unverified_user():
    user = _make_unverified_user()
    assert _should_send_email(user) is False


def test_should_send_email_false_for_user_without_email():
    user = User.objects.create_user(username=f"nomail-{_uid()}", password="pass", email="")
    assert _should_send_email(user) is False


def test_should_send_email_true_for_user_without_profile():
    user = _make_user()
    assert _should_send_email(user) is True


def test_template_for_application_approved():
    notif = _make_notification(_make_user(), event_type="application.review.accepted")
    assert "application_approved" in _template_for_notification(notif)


def test_template_for_application_rejected():
    notif = _make_notification(_make_user(), event_type="application.review.rejected")
    assert "application_rejected" in _template_for_notification(notif)


def test_template_for_new_message():
    notif = _make_notification(_make_user(), event_type="messaging.new_message")
    assert "message_received" in _template_for_notification(notif)


def test_template_fallback_for_unknown_event():
    notif = _make_notification(_make_user(), event_type="unknown.event")
    assert "notification.html" in _template_for_notification(notif)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_email_sent_for_verified_user():
    user = _make_verified_user()
    notif = _make_notification(user, title="Заявка принята")

    _send_email_for_notification(notif.pk)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]
    assert "Заявка принята" in mail.outbox[0].subject


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
def test_email_skipped_for_unverified_user():
    user = _make_unverified_user()
    notif = _make_notification(user, title="Тест")

    _send_email_for_notification(notif.pk)

    assert len(mail.outbox) == 0
    notif.refresh_from_db()
    assert notif.email_status == NotificationEmailStatus.SKIPPED


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_email_is_multipart_html_and_plain():
    user = _make_verified_user()
    notif = _make_notification(user, body="Текст письма")

    _send_email_for_notification(notif.pk)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.body == "Текст письма"
    alternatives = getattr(msg, "alternatives", [])
    assert any("text/html" in mime for _, mime in alternatives)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_email_subject_has_dsa_prefix():
    user = _make_verified_user()
    notif = _make_notification(user, title="Новый проект")

    _send_email_for_notification(notif.pk)

    assert mail.outbox[0].subject == "DSA: Новый проект"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_email_status_set_to_sent_after_success():
    user = _make_verified_user()
    notif = _make_notification(user)

    _send_email_for_notification(notif.pk)

    notif.refresh_from_db()
    assert notif.email_status == NotificationEmailStatus.SENT
    assert notif.email_sent_at is not None


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_email_status_set_to_failed_on_error(monkeypatch):
    user = _make_verified_user()
    notif = _make_notification(user)

    def _raise(*a, **kw):
        raise Exception("SMTP error")

    monkeypatch.setattr("django.core.mail.EmailMultiAlternatives.send", _raise)

    _send_email_for_notification(notif.pk)

    notif.refresh_from_db()
    assert notif.email_status == NotificationEmailStatus.FAILED
    assert "SMTP error" in notif.email_error


def test_create_notifications_creates_notification_per_recipient():
    u1 = _make_user()
    u2 = _make_user()
    spec = NotificationSpec(
        event_type="test.event",
        title="Hello",
        body="World",
        target_type="project",
        target_id="42",
    )
    result = create_notifications(recipients=[u1, u2], spec=spec)
    assert len(result) == 2
    assert Notification.objects.filter(event_type="test.event").count() == 2


def test_create_notifications_deduplicates_by_dedupe_key():
    user = _make_user()
    spec = NotificationSpec(
        event_type="test.dedup",
        title="Dedup",
        body="",
        target_type="x",
        target_id="1",
        dedupe_key="unique-key-abc",
    )
    create_notifications(recipients=[user], spec=spec)
    create_notifications(recipients=[user], spec=spec)
    assert Notification.objects.filter(dedupe_key="unique-key-abc").count() == 1


def test_create_notifications_skips_none_recipients():
    spec = NotificationSpec(
        event_type="test.none",
        title="Test",
        body="",
        target_type="x",
        target_id="1",
    )
    result = create_notifications(recipients=[None, None], spec=spec)
    assert result == []


# ---------------------------------------------------------------------------
# Messaging digest: one email per recipient per day
# ---------------------------------------------------------------------------

@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_messaging_email_subject_is_generic_digest():
    """Email subject must be a generic digest line, not a per-thread title."""
    user = _make_verified_user()
    notif = _make_notification(user, event_type="messaging.new_message", title="Новое сообщение в «Проект А»")

    assert _email_subject(notif) == "DSA: У вас новые сообщения"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_messaging_first_email_of_day_is_sent():
    """When no messaging email has been sent today, the first notification triggers one."""
    user = _make_verified_user()
    notif = _make_notification(user, event_type="messaging.new_message")

    _send_email_for_notification(notif.pk)

    assert len(mail.outbox) == 1
    notif.refresh_from_db()
    assert notif.email_status == NotificationEmailStatus.SENT


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_messaging_second_notification_same_day_is_skipped():
    """A second messaging notification on the same day must be skipped."""
    user = _make_verified_user()

    # Simulate a notification already sent today.
    already_sent = _make_notification(user, event_type="messaging.new_message")
    already_sent.email_status = NotificationEmailStatus.SENT
    already_sent.email_sent_at = timezone.now()
    already_sent.save(update_fields=["email_status", "email_sent_at"])

    second = _make_notification(user, event_type="messaging.new_message")
    _send_email_for_notification(second.pk)

    assert len(mail.outbox) == 0
    second.refresh_from_db()
    assert second.email_status == NotificationEmailStatus.SKIPPED


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_messaging_email_sent_again_after_previous_day():
    """A notification sent yesterday must not block today's email."""
    user = _make_verified_user()

    yesterday_notif = _make_notification(user, event_type="messaging.new_message")
    yesterday_notif.email_status = NotificationEmailStatus.SENT
    yesterday_notif.email_sent_at = timezone.now() - timedelta(days=1)
    yesterday_notif.save(update_fields=["email_status", "email_sent_at"])

    today_notif = _make_notification(user, event_type="messaging.new_message")
    _send_email_for_notification(today_notif.pk)

    assert len(mail.outbox) == 1
    today_notif.refresh_from_db()
    assert today_notif.email_status == NotificationEmailStatus.SENT


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_messaging_digest_email_contains_messages_link():
    """The digest email body must link to /messages/, not a specific thread."""
    user = _make_verified_user()
    notif = _make_notification(user, event_type="messaging.new_message")

    _send_email_for_notification(notif.pk)

    assert len(mail.outbox) == 1
    html_body = mail.outbox[0].alternatives[0][0]
    assert "/messages/" in html_body


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_messaging_digest_skipping_does_not_affect_other_event_types():
    """Digest deduplication must only apply to messaging.new_message, not other events."""
    user = _make_verified_user()

    # Mark a messaging notification as already sent today.
    msg_notif = _make_notification(user, event_type="messaging.new_message")
    msg_notif.email_status = NotificationEmailStatus.SENT
    msg_notif.email_sent_at = timezone.now()
    msg_notif.save(update_fields=["email_status", "email_sent_at"])

    # An application notification for the same user must still be sent.
    app_notif = _make_notification(user, event_type="application.review.accepted", title="Заявка принята")
    _send_email_for_notification(app_notif.pk)

    assert len(mail.outbox) == 1
    app_notif.refresh_from_db()
    assert app_notif.email_status == NotificationEmailStatus.SENT


# ---------------------------------------------------------------------------
# retry_failed_emails management command
# ---------------------------------------------------------------------------

def test_retry_failed_emails_no_failed_notifications(capsys):
    """When there are no FAILED notifications the command prints a success message."""
    call_command("retry_failed_emails")
    out = capsys.readouterr().out
    assert "No failed notifications found" in out


def test_retry_failed_emails_dry_run_does_not_send(capsys):
    """--dry-run lists FAILED notifications but does not call _send_email_for_notification."""
    user = _make_verified_user()
    notif = _make_notification(user)
    notif.email_status = NotificationEmailStatus.FAILED
    notif.email_error = "SMTP timeout"
    notif.save(update_fields=["email_status", "email_error"])

    call_command("retry_failed_emails", dry_run=True)

    out = capsys.readouterr().out
    assert "dry-run" in out.lower() or "Dry run" in out
    notif.refresh_from_db()
    assert notif.email_status == NotificationEmailStatus.FAILED


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_retry_failed_emails_sends_and_marks_sent(capsys):
    """A FAILED notification is reset to PENDING, email is sent, status becomes SENT."""
    user = _make_verified_user()
    notif = _make_notification(user, title="Retry me")
    notif.email_status = NotificationEmailStatus.FAILED
    notif.email_error = "Previous SMTP error"
    notif.save(update_fields=["email_status", "email_error"])

    call_command("retry_failed_emails")

    notif.refresh_from_db()
    assert notif.email_status == NotificationEmailStatus.SENT
    assert len(mail.outbox) == 1


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_retry_failed_emails_respects_limit(capsys):
    """--limit N means at most N notifications are retried in one run."""
    user = _make_verified_user()
    for i in range(3):
        n = _make_notification(user, title=f"Failed {i}")
        n.email_status = NotificationEmailStatus.FAILED
        n.save(update_fields=["email_status"])

    call_command("retry_failed_emails", limit=1)

    sent_count = Notification.objects.filter(
        recipient=user, email_status=NotificationEmailStatus.SENT
    ).count()
    assert sent_count == 1


def test_retry_failed_emails_invalid_limit_raises():
    """--limit 0 must raise CommandError immediately."""
    with pytest.raises((CommandError, SystemExit)):
        call_command("retry_failed_emails", limit=0)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@dsa.test",
    SITE_URL="https://dsa.test",
)
def test_retry_failed_emails_counts_still_failed(capsys, monkeypatch):
    """When _send_email_for_notification fails again, still_failed is reported."""
    user = _make_verified_user()
    notif = _make_notification(user)
    notif.email_status = NotificationEmailStatus.FAILED
    notif.save(update_fields=["email_status"])

    def _always_fail(notification_id: int) -> None:
        Notification.objects.filter(pk=notification_id).update(
            email_status=NotificationEmailStatus.FAILED,
            email_error="SMTP still broken",
        )

    monkeypatch.setattr(
        "apps.notifications.management.commands.retry_failed_emails._send_email_for_notification",
        _always_fail,
    )

    call_command("retry_failed_emails")

    out = capsys.readouterr().out
    assert "still failed" in out.lower() or "still_failed" in out or "1" in out
    notif.refresh_from_db()
    assert notif.email_status == NotificationEmailStatus.FAILED
