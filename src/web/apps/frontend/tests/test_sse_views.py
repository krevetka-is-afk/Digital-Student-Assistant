from __future__ import annotations

import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from apps.notifications.models import Notification, NotificationEmailStatus
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()

pytestmark = pytest.mark.django_db


def _uid():
    return uuid4().hex[:8]


def _make_user():
    return User.objects.create_user(username=f"user-{_uid()}", password="pass")


def _make_notification(user, title="Test", body="Body", event_type="test.event"):
    return Notification.objects.create(
        recipient=user,
        event_type=event_type,
        title=title,
        body=body,
        target_type="test",
        target_id="1",
        email_status=NotificationEmailStatus.SKIPPED,
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_sse_stream_redirects_unauthenticated():
    response = Client().get(reverse("frontend:notification_stream"))
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# Content-Type and headers
# ---------------------------------------------------------------------------

def test_sse_stream_returns_event_stream_content_type():
    user = _make_user()
    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(1)):
        response = client.get(reverse("frontend:notification_stream"))
        assert response.status_code == 200
        assert "text/event-stream" in response.get("Content-Type", "")
        b"".join(response.streaming_content)


def test_sse_stream_content_type_declares_utf8():
    """charset=utf-8 must be explicit so tools (DevTools, curl) render Cyrillic correctly."""
    user = _make_user()
    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(1)):
        response = client.get(reverse("frontend:notification_stream"))
        assert "charset=utf-8" in response.get("Content-Type", "").lower()
        b"".join(response.streaming_content)


def test_sse_stream_has_no_cache_header():
    user = _make_user()
    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(1)):
        response = client.get(reverse("frontend:notification_stream"))
        assert response.get("Cache-Control") == "no-cache"
        b"".join(response.streaming_content)


def test_sse_stream_has_x_accel_buffering_no():
    user = _make_user()
    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(1)):
        response = client.get(reverse("frontend:notification_stream"))
        assert response.get("X-Accel-Buffering") == "no"
        b"".join(response.streaming_content)


# ---------------------------------------------------------------------------
# Init event
# ---------------------------------------------------------------------------

def test_sse_stream_init_event_contains_unread_count():
    user = _make_user()
    _make_notification(user, title="Unread 1")
    _make_notification(user, title="Unread 2")

    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(1)):
        response = client.get(reverse("frontend:notification_stream"))
        content = b"".join(response.streaming_content).decode()

    assert '"type": "init"' in content or '"type":"init"' in content
    assert '"unread_count": 2' in content or '"unread_count":2' in content


def test_sse_stream_init_unread_count_zero_when_no_notifications():
    user = _make_user()
    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(1)):
        response = client.get(reverse("frontend:notification_stream"))
        content = b"".join(response.streaming_content).decode()

    assert '"unread_count": 0' in content or '"unread_count":0' in content


def test_sse_stream_contains_retry_field():
    """retry: 3000 must appear in the stream so the browser knows the reconnect interval."""
    user = _make_user()
    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(1)):
        response = client.get(reverse("frontend:notification_stream"))
        content = b"".join(response.streaming_content).decode()

    assert "retry: 3000" in content


# ---------------------------------------------------------------------------
# Notification events
# ---------------------------------------------------------------------------

def test_sse_stream_yields_new_notification():
    user = _make_user()
    anchor = _make_notification(user, title="Already seen")
    target = _make_notification(user, title="Новое сообщение", event_type="messaging.new_message")

    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(2)):
        response = client.get(
            reverse("frontend:notification_stream") + f"?lastId={anchor.pk}"
        )
        content = b"".join(response.streaming_content).decode()

    assert '"type": "notification"' in content or '"type":"notification"' in content
    assert "Новое сообщение" in content


def test_sse_stream_does_not_yield_old_notifications():
    user = _make_user()
    notif = _make_notification(user, title="Old notif")

    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(2)):
        response = client.get(
            reverse("frontend:notification_stream") + f"?lastId={notif.pk}"
        )
        content = b"".join(response.streaming_content).decode()

    assert "Old notif" not in content


def test_sse_stream_heartbeat_when_no_new_notifications():
    user = _make_user()
    notif = _make_notification(user, title="Already seen")

    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(2)):
        response = client.get(
            reverse("frontend:notification_stream") + f"?lastId={notif.pk}"
        )
        content = b"".join(response.streaming_content).decode()

    assert ": heartbeat" in content


# ---------------------------------------------------------------------------
# Anti-flood: any lastId <= 0 must skip existing notifications
# ---------------------------------------------------------------------------

def test_sse_stream_zero_last_id_triggers_anti_flood():
    """lastId=0 (fresh connect) must not replay existing notifications as toasts."""
    user = _make_user()
    _make_notification(user, title="Old notification")

    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(2)):
        response = client.get(reverse("frontend:notification_stream") + "?lastId=0")
        content = b"".join(response.streaming_content).decode()

    assert "Old notification" not in content


def test_sse_stream_negative_last_id_triggers_anti_flood():
    """lastId<0 must be treated the same as 0 — existing notifications are skipped."""
    user = _make_user()
    _make_notification(user, title="Old notification")

    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(2)):
        response = client.get(reverse("frontend:notification_stream") + "?lastId=-99")
        content = b"".join(response.streaming_content).decode()

    assert "Old notification" not in content


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------

def test_sse_stream_does_not_leak_other_users_notifications():
    alice = _make_user()
    bob = _make_user()
    anchor = _make_notification(alice, title="Alice anchor")
    _make_notification(bob, title="Bob private")

    client = Client()
    client.force_login(alice)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(2)):
        response = client.get(
            reverse("frontend:notification_stream") + f"?lastId={anchor.pk}"
        )
        content = b"".join(response.streaming_content).decode()

    assert "Bob private" not in content


# ---------------------------------------------------------------------------
# SSE id: field and Last-Event-ID header
# ---------------------------------------------------------------------------

def test_sse_notification_event_contains_id_field():
    user = _make_user()
    anchor = _make_notification(user, title="Anchor")
    target = _make_notification(user, title="With ID")

    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(2)):
        response = client.get(
            reverse("frontend:notification_stream") + f"?lastId={anchor.pk}"
        )
        content = b"".join(response.streaming_content).decode()

    assert f"id: {target.pk}" in content


def test_sse_last_event_id_header_respected():
    """Browser sends Last-Event-ID on auto-reconnect; server must resume from there."""
    user = _make_user()
    old = _make_notification(user, title="Old")
    new = _make_notification(user, title="New after reconnect")

    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(2)):
        response = client.get(
            reverse("frontend:notification_stream"),
            HTTP_LAST_EVENT_ID=str(old.pk),
        )
        content = b"".join(response.streaming_content).decode()

    assert "Old" not in content
    assert "New after reconnect" in content


# ---------------------------------------------------------------------------
# unread_count in notification event
# ---------------------------------------------------------------------------

def test_sse_notification_event_contains_unread_count():
    user = _make_user()
    anchor = _make_notification(user, title="Anchor")
    _make_notification(user, title="Unread A")
    _make_notification(user, title="Unread B")

    client = Client()
    client.force_login(user)

    with patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(2)):
        response = client.get(
            reverse("frontend:notification_stream") + f"?lastId={anchor.pk}"
        )
        content = b"".join(response.streaming_content).decode()

    notification_events = [
        json.loads(line[len("data: "):])
        for line in content.splitlines()
        if line.startswith("data: ") and (
            '"type": "notification"' in line or '"type":"notification"' in line
        )
    ]
    assert any("unread_count" in e for e in notification_events)


# ---------------------------------------------------------------------------
# DB error resilience
# ---------------------------------------------------------------------------

def test_sse_stream_db_error_in_loop_falls_back_to_heartbeat():
    """A DB error during the poll query must not crash the stream — yield heartbeat."""
    user = _make_user()
    notif = _make_notification(user, title="Seen")

    client = Client()
    client.force_login(user)

    original_filter = Notification.objects.filter
    call_count = {"n": 0}

    def patched_filter(*args, **kwargs):
        call_count["n"] += 1
        # First call: init unread_count (must succeed).
        # Second call onwards: loop poll query — raise to simulate DB hiccup.
        if call_count["n"] > 1:
            raise Exception("Simulated DB failure")
        return original_filter(*args, **kwargs)

    with patch("apps.frontend.views.sse.Notification.objects.filter",
               side_effect=patched_filter), \
         patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(2)):
        response = client.get(
            reverse("frontend:notification_stream") + f"?lastId={notif.pk}"
        )
        content = b"".join(response.streaming_content).decode()

    assert ": heartbeat" in content


def test_sse_stream_unread_count_error_falls_back_to_heartbeat():
    """A DB error on the unread_count re-query (after finding new items) must also
    fall back to heartbeat rather than crashing the stream."""
    user = _make_user()
    anchor = _make_notification(user, title="Anchor")
    _make_notification(user, title="New item")

    client = Client()
    client.force_login(user)

    original_filter = Notification.objects.filter
    call_count = {"n": 0}

    def patched_filter(*args, **kwargs):
        call_count["n"] += 1
        # Call 1: init unread_count — succeeds.
        # Call 2: poll query (finds new item) — succeeds.
        # Call 3: unread_count re-query after finding items — raises.
        if call_count["n"] == 3:
            raise Exception("Simulated unread_count failure")
        return original_filter(*args, **kwargs)

    with patch("apps.frontend.views.sse.Notification.objects.filter",
               side_effect=patched_filter), \
         patch("apps.frontend.views.sse.time.sleep"), \
         patch("apps.frontend.views.sse.range", return_value=range(2)):
        response = client.get(
            reverse("frontend:notification_stream") + f"?lastId={anchor.pk}"
        )
        content = b"".join(response.streaming_content).decode()

    assert ": heartbeat" in content
