from uuid import uuid4

from apps.users.email_verification import create_signup_verification, extract_code_from_message
from apps.users.models import EmailVerificationCode, UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse


def _make_unverified_user(*, email: str = "pending@example.com"):
    suffix = uuid4().hex[:8]
    user = get_user_model().objects.create_user(
        username=f"{email.split('@')[0]}-{suffix}",
        email=email,
        password="password123",
        is_active=False,
    )
    UserProfile.objects.create(user=user, role=UserRole.STUDENT)
    return user


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_registration_sends_code_and_keeps_user_logged_out():
    client = Client()
    baseline = len(getattr(mail, "outbox", []))
    email = f"new-student-{uuid4().hex[:8]}@example.com"

    response = client.post(
        reverse("frontend:auth"),
        data={
            "tab": "register",
            "email": email,
            "password": "password123",
            "name": "New Student",
            "role": UserRole.STUDENT,
        },
    )

    user = get_user_model().objects.get(email=email)
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("frontend:verify_email"))
    assert user.is_active is False
    assert user.profile.email_verified_at is None
    assert EmailVerificationCode.objects.filter(user=user, consumed_at__isnull=True).exists()
    assert len(mail.outbox) == baseline + 1
    assert extract_code_from_message(mail.outbox[-1].body) is not None
    assert "_auth_user_id" not in client.session


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_correct_verification_code_activates_and_logs_in_user():
    user = _make_unverified_user(email=f"verify-me-{uuid4().hex[:8]}@example.com")
    create_signup_verification(user)
    code = extract_code_from_message(mail.outbox[-1].body)
    assert code is not None

    client = Client()
    response = client.post(
        reverse("frontend:verify_email"),
        data={"email": user.email, "code": code},
    )

    user.refresh_from_db()
    user.profile.refresh_from_db()
    assert response.status_code == 302
    assert response["Location"] == reverse("frontend:project_list")
    assert user.is_active is True
    assert user.profile.email_verified_at is not None
    assert str(user.pk) == client.session["_auth_user_id"]


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_login_blocks_unverified_user_after_valid_password():
    user = _make_unverified_user(email=f"blocked-{uuid4().hex[:8]}@example.com")
    create_signup_verification(user)
    client = Client()

    response = client.post(
        reverse("frontend:auth"),
        data={
            "tab": "login",
            "email": user.email,
            "password": "password123",
        },
    )

    assert response.status_code == 200
    assert reverse("frontend:verify_email").encode() in response.content
    assert "_auth_user_id" not in client.session
