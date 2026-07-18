from __future__ import annotations

from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.messaging.models import Message, Thread

User = get_user_model()

pytestmark = pytest.mark.django_db


def _uid():
    return uuid4().hex[:8]


def _make_user():
    return User.objects.create_user(username=f"user-{_uid()}", password="pass")


def _make_thread(user_a, user_b, subject="Test subject"):
    thread = Thread.objects.create(subject=subject)
    thread.participants.add(user_a, user_b)
    return thread


def _make_message(thread, sender, body="Hello"):
    return Message.objects.create(thread=thread, sender=sender, body=body)


def test_thread_list_redirects_unauthenticated():
    response = Client().get(reverse("messaging:thread_list"))
    assert response.status_code == 302
    assert "login" in response["Location"] or "auth" in response["Location"]


def test_thread_list_shows_own_threads():
    alice = _make_user()
    bob = _make_user()
    stranger = _make_user()

    thread = _make_thread(alice, bob, subject="Alice–Bob")
    _make_thread(bob, stranger, subject="Bob–Stranger")

    client = Client()
    client.force_login(alice)
    response = client.get(reverse("messaging:thread_list"))

    assert response.status_code == 200
    assert "Alice–Bob" in response.content.decode()
    assert "Bob–Stranger" not in response.content.decode()


def test_thread_list_shows_unread_count():
    alice = _make_user()
    bob = _make_user()
    thread = _make_thread(alice, bob)
    _make_message(thread, bob, "Unread message")

    client = Client()
    client.force_login(alice)
    response = client.get(reverse("messaging:thread_list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "1" in content


def test_thread_list_empty_state():
    user = _make_user()
    client = Client()
    client.force_login(user)
    response = client.get(reverse("messaging:thread_list"))
    assert response.status_code == 200
    assert "Нет диалогов" in response.content.decode()


def test_thread_create_get_renders_form():
    user = _make_user()
    client = Client()
    client.force_login(user)
    response = client.get(reverse("messaging:thread_create"))
    assert response.status_code == 200
    assert "Новое сообщение" in response.content.decode()


def test_thread_create_get_preselects_recipient_via_to_param():
    alice = _make_user()
    bob = _make_user()
    client = Client()
    client.force_login(alice)
    response = client.get(reverse("messaging:thread_create") + f"?to={bob.pk}")
    assert response.status_code == 200
    assert f'name="recipient" value="{bob.pk}"' in response.content.decode()


def test_thread_create_post_creates_thread_and_redirects():
    alice = _make_user()
    bob = _make_user()
    client = Client()
    client.force_login(alice)

    response = client.post(reverse("messaging:thread_create"), {
        "recipient": bob.pk,
        "subject": "Hello Bob",
        "body": "First message",
    })

    assert Thread.objects.filter(subject="Hello Bob").exists()
    thread = Thread.objects.get(subject="Hello Bob")
    assert thread.messages.count() == 1
    assert response.status_code == 302


def test_thread_create_post_missing_fields_shows_errors():
    alice = _make_user()
    client = Client()
    client.force_login(alice)

    response = client.post(reverse("messaging:thread_create"), {
        "recipient": "",
        "subject": "",
        "body": "",
    })

    assert response.status_code == 200
    assert Thread.objects.count() == 0
    content = response.content.decode()
    assert "Выберите получателя" in content or "Укажите тему" in content or "Введите текст" in content


def test_thread_create_redirects_unauthenticated():
    response = Client().get(reverse("messaging:thread_create"))
    assert response.status_code == 302



def test_thread_open_creates_thread_and_redirects_to_detail():
    alice = _make_user()
    bob = _make_user()
    client = Client()
    client.force_login(alice)

    response = client.get(reverse("messaging:thread_open") + f"?to={bob.pk}")

    assert response.status_code == 302
    assert Thread.objects.filter(participants=alice).filter(participants=bob).exists()
    thread = Thread.objects.filter(participants=alice).filter(participants=bob).first()
    assert reverse("messaging:thread_detail", kwargs={"pk": thread.pk}) in response["Location"]


def test_thread_open_reuses_existing_thread():
    alice = _make_user()
    bob = _make_user()
    existing = _make_thread(alice, bob, subject="Уже существует")
    client = Client()
    client.force_login(alice)

    client.get(reverse("messaging:thread_open") + f"?to={bob.pk}")
    client.get(reverse("messaging:thread_open") + f"?to={bob.pk}")

    assert Thread.objects.filter(participants=alice).filter(participants=bob).count() == 1


def test_thread_open_redirects_to_existing_thread_detail():
    alice = _make_user()
    bob = _make_user()
    existing = _make_thread(alice, bob, subject="Старый диалог")
    client = Client()
    client.force_login(alice)

    response = client.get(reverse("messaging:thread_open") + f"?to={bob.pk}")

    assert response.status_code == 302
    assert str(existing.pk) in response["Location"]


def test_thread_open_self_redirect_goes_to_list():
    alice = _make_user()
    client = Client()
    client.force_login(alice)

    response = client.get(reverse("messaging:thread_open") + f"?to={alice.pk}")

    assert response.status_code == 302
    assert reverse("messaging:thread_list") in response["Location"]


def test_thread_open_invalid_to_param_goes_to_list():
    alice = _make_user()
    client = Client()
    client.force_login(alice)

    response = client.get(reverse("messaging:thread_open") + "?to=notanumber")

    assert response.status_code == 302
    assert reverse("messaging:thread_list") in response["Location"]


def test_thread_open_redirects_unauthenticated():
    response = Client().get(reverse("messaging:thread_open") + "?to=1")
    assert response.status_code == 302


def test_thread_detail_shows_messages():
    alice = _make_user()
    bob = _make_user()
    thread = _make_thread(alice, bob)
    _make_message(thread, bob, "Hi Alice!")

    client = Client()
    client.force_login(alice)
    response = client.get(reverse("messaging:thread_detail", kwargs={"pk": thread.pk}))

    assert response.status_code == 200
    assert "Hi Alice!" in response.content.decode()


def test_thread_detail_marks_messages_as_read():
    alice = _make_user()
    bob = _make_user()
    thread = _make_thread(alice, bob)
    msg = _make_message(thread, bob, "Read me")

    assert msg.read_by.filter(pk=alice.pk).count() == 0

    client = Client()
    client.force_login(alice)
    client.get(reverse("messaging:thread_detail", kwargs={"pk": thread.pk}))

    msg.refresh_from_db()
    assert msg.read_by.filter(pk=alice.pk).exists()


def test_thread_detail_outsider_gets_404():
    alice = _make_user()
    bob = _make_user()
    stranger = _make_user()
    thread = _make_thread(alice, bob)

    client = Client()
    client.force_login(stranger)
    response = client.get(reverse("messaging:thread_detail", kwargs={"pk": thread.pk}))
    assert response.status_code == 404


def test_thread_detail_post_sends_reply():
    alice = _make_user()
    bob = _make_user()
    thread = _make_thread(alice, bob)

    client = Client()
    client.force_login(alice)
    response = client.post(
        reverse("messaging:thread_detail", kwargs={"pk": thread.pk}),
        {"body": "Reply from Alice"},
    )

    assert response.status_code == 302
    assert thread.messages.filter(body="Reply from Alice", sender=alice).exists()


def test_thread_detail_post_empty_body_ignored():
    alice = _make_user()
    bob = _make_user()
    thread = _make_thread(alice, bob)

    client = Client()
    client.force_login(alice)
    client.post(
        reverse("messaging:thread_detail", kwargs={"pk": thread.pk}),
        {"body": "   "},
    )

    assert thread.messages.count() == 0


def test_thread_detail_redirects_unauthenticated():
    alice = _make_user()
    bob = _make_user()
    thread = _make_thread(alice, bob)

    response = Client().get(reverse("messaging:thread_detail", kwargs={"pk": thread.pk}))
    assert response.status_code == 302


def test_unread_messages_count_in_context():
    alice = _make_user()
    bob = _make_user()
    thread = _make_thread(alice, bob)
    _make_message(thread, bob, "Unread 1")
    _make_message(thread, bob, "Unread 2")

    client = Client()
    client.force_login(alice)
    response = client.get(reverse("messaging:thread_list"))

    assert response.context["unread_messages_count"] == 2


def test_unread_messages_count_excludes_own_messages():
    alice = _make_user()
    bob = _make_user()
    thread = _make_thread(alice, bob)
    _make_message(thread, alice, "Own message")

    client = Client()
    client.force_login(alice)
    response = client.get(reverse("messaging:thread_list"))

    assert response.context["unread_messages_count"] == 0


def test_unread_count_drops_to_zero_after_reading():
    alice = _make_user()
    bob = _make_user()
    thread = _make_thread(alice, bob)
    _make_message(thread, bob, "New message")

    client = Client()
    client.force_login(alice)

    before = client.get(reverse("messaging:thread_list")).context["unread_messages_count"]
    assert before == 1

    client.get(reverse("messaging:thread_detail", kwargs={"pk": thread.pk}))

    after = client.get(reverse("messaging:thread_list")).context["unread_messages_count"]
    assert after == 0


# --- N+1 annotation ---

def test_thread_list_ctx_unread_count_via_annotation():
    """_thread_list_ctx returns correct per-thread unread count via annotation, not N+1."""
    alice = _make_user()
    bob = _make_user()
    carol = _make_user()

    t1 = _make_thread(alice, bob)
    _make_message(t1, bob, "msg1")
    _make_message(t1, bob, "msg2")
    _make_message(t1, alice, "own message")  # should NOT be counted

    t2 = _make_thread(alice, carol)
    _make_message(t2, carol, "hi alice")

    client = Client()
    client.force_login(alice)
    response = client.get(reverse("messaging:thread_list"))

    pairs = {t.pk: count for t, count, _ in response.context["threads_with_meta"]}
    assert pairs[t1.pk] == 2
    assert pairs[t2.pk] == 1


def test_last_message_uses_prefetch_cache():
    """Thread.last_message() returns the most recent message without a DB hit when
    messages are already prefetched in order."""
    alice = _make_user()
    bob = _make_user()
    thread = _make_thread(alice, bob)
    _make_message(thread, alice, "first")
    last = _make_message(thread, bob, "second")

    from django.db.models import Prefetch
    from apps.messaging.models import Message
    t = (
        Thread.objects.filter(pk=thread.pk)
        .prefetch_related(Prefetch("messages", queryset=Message.objects.order_by("-created_at")))
        .get()
    )
    assert t.last_message().pk == last.pk


# --- Body max-length validation ---

def test_thread_detail_post_body_too_long_shows_error():
    alice = _make_user()
    bob = _make_user()
    thread = _make_thread(alice, bob)

    client = Client()
    client.force_login(alice)
    response = client.post(
        reverse("messaging:thread_detail", kwargs={"pk": thread.pk}),
        {"body": "x" * 5001},
    )

    assert response.status_code == 200
    assert thread.messages.count() == 0
    assert "5000" in response.content.decode()


def test_thread_create_post_body_too_long_shows_error():
    alice = _make_user()
    bob = _make_user()

    client = Client()
    client.force_login(alice)
    response = client.post(reverse("messaging:thread_create"), {
        "recipient": bob.pk,
        "subject": "Test",
        "body": "y" * 5001,
    })

    assert response.status_code == 200
    assert Thread.objects.count() == 0
    assert "5000" in response.content.decode()


# --- Self-messaging prevention ---

def test_thread_create_post_self_messaging_shows_error():
    alice = _make_user()

    client = Client()
    client.force_login(alice)
    response = client.post(reverse("messaging:thread_create"), {
        "recipient": alice.pk,
        "subject": "Myself",
        "body": "Hello me",
    })

    assert response.status_code == 200
    assert Thread.objects.count() == 0
    assert "самому себе" in response.content.decode()


# --- thread_create deduplication ---

def test_thread_create_post_reuses_existing_thread():
    """Posting to thread_create when a thread already exists should not create a duplicate."""
    alice = _make_user()
    bob = _make_user()
    existing = _make_thread(alice, bob, subject="Существующий диалог")

    client = Client()
    client.force_login(alice)
    response = client.post(reverse("messaging:thread_create"), {
        "recipient": bob.pk,
        "subject": "Новая тема",
        "body": "Привет снова",
    })

    assert response.status_code == 302
    assert Thread.objects.filter(participants=alice).filter(participants=bob).count() == 1
    existing.refresh_from_db()
    assert existing.messages.filter(body="Привет снова").exists()


def test_thread_create_post_creates_new_thread_if_none_exists():
    alice = _make_user()
    bob = _make_user()

    client = Client()
    client.force_login(alice)
    response = client.post(reverse("messaging:thread_create"), {
        "recipient": bob.pk,
        "subject": "Новый диалог",
        "body": "Привет!",
    })

    assert response.status_code == 302
    assert Thread.objects.filter(participants=alice).filter(participants=bob).count() == 1
