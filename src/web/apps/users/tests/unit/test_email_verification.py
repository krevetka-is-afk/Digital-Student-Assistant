from datetime import timedelta
from uuid import uuid4

import pytest
from apps.users.email_verification import (
    create_signup_verification,
    extract_code_from_message,
    resend_signup_code,
    verify_signup_code,
)
from apps.users.models import EmailVerificationCode, UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone


@pytest.fixture
def unverified_user():
    suffix = uuid4().hex[:8]
    user = get_user_model().objects.create_user(
        username=f"pending-user-{suffix}",
        email=f"pending-{suffix}@example.com",
        password="password123",
        is_active=False,
    )
    UserProfile.objects.create(user=user, role=UserRole.STUDENT)
    return user


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_create_signup_verification_sends_email_and_invalidates_previous_codes(unverified_user):
    baseline = len(getattr(mail, "outbox", []))
    first_code = create_signup_verification(unverified_user)
    second_code = create_signup_verification(unverified_user)

    first_code.refresh_from_db()
    second_code.refresh_from_db()

    assert len(mail.outbox) == baseline + 2
    assert extract_code_from_message(mail.outbox[-1].body)
    assert first_code.consumed_at is not None
    assert second_code.consumed_at is None
    assert second_code.email == unverified_user.email


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_create_signup_verification_uses_user_email_as_recipient(unverified_user):
    create_signup_verification(unverified_user)

    sent_message = mail.outbox[-1]

    assert sent_message.to == [unverified_user.email]
    assert "Digital Student Assistant" in sent_message.subject
    assert extract_code_from_message(sent_message.body) is not None


def test_extract_code_from_message_returns_none_without_six_digit_code():
    assert extract_code_from_message("no verification code here") is None
    assert extract_code_from_message("code 12345 is too short") is None


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_create_signup_verification_normalizes_stored_email():
    suffix = uuid4().hex[:8]
    user = get_user_model().objects.create_user(
        username=f"pending-uppercase-{suffix}",
        email=f"Pending-{suffix}@Example.COM",
        password="password123",
        is_active=False,
    )
    UserProfile.objects.create(user=user, role=UserRole.STUDENT)

    verification = create_signup_verification(user)

    assert verification.email == user.email.lower()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_verify_signup_code_activates_user_and_marks_profile_verified(unverified_user):
    create_signup_verification(unverified_user)
    code = extract_code_from_message(mail.outbox[-1].body)
    assert code is not None

    result = verify_signup_code(email=unverified_user.email, code=code)

    unverified_user.refresh_from_db()
    unverified_user.profile.refresh_from_db()
    verification = EmailVerificationCode.objects.get(user=unverified_user)

    assert result.success is True
    assert result.reason == "verified"
    assert unverified_user.is_active is True
    assert unverified_user.profile.email_verified_at is not None
    assert verification.consumed_at is not None


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_verify_signup_code_matches_email_case_insensitively(unverified_user):
    create_signup_verification(unverified_user)
    code = extract_code_from_message(mail.outbox[-1].body)
    assert code is not None

    result = verify_signup_code(email=unverified_user.email.upper(), code=code)

    assert result.success is True
    assert result.reason == "verified"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_verify_signup_code_cannot_be_reused_after_success(unverified_user):
    create_signup_verification(unverified_user)
    code = extract_code_from_message(mail.outbox[-1].body)
    assert code is not None

    first_result = verify_signup_code(email=unverified_user.email, code=code)
    second_result = verify_signup_code(email=unverified_user.email, code=code)

    assert first_result.success is True
    assert first_result.reason == "verified"
    assert second_result.success is False
    assert second_result.reason == "invalid"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_verify_signup_code_rejects_invalid_code_and_tracks_attempts(unverified_user):
    create_signup_verification(unverified_user)

    result = verify_signup_code(email=unverified_user.email, code="000000")
    verification = EmailVerificationCode.objects.get(user=unverified_user)

    assert result.success is False
    assert result.reason == "invalid"
    assert verification.attempt_count == 1


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_verify_signup_code_rejects_blank_input(unverified_user):
    create_signup_verification(unverified_user)

    blank_email = verify_signup_code(email="", code="123456")
    blank_code = verify_signup_code(email=unverified_user.email, code="")
    unknown_email = verify_signup_code(email="missing@example.com", code="123456")

    assert blank_email.success is False
    assert blank_email.reason == "missing_fields"
    assert blank_code.success is False
    assert blank_code.reason == "missing_fields"
    assert unknown_email.success is False
    assert unknown_email.reason == "invalid"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_VERIFICATION_MAX_ATTEMPTS=2,
)
def test_verify_signup_code_blocks_after_max_attempts(unverified_user):
    create_signup_verification(unverified_user)
    code = extract_code_from_message(mail.outbox[-1].body)
    assert code is not None

    first = verify_signup_code(email=unverified_user.email, code="000000")
    second = verify_signup_code(email=unverified_user.email, code="111111")
    final = verify_signup_code(email=unverified_user.email, code=code)
    verification = EmailVerificationCode.objects.get(user=unverified_user)

    assert first.reason == "invalid"
    assert second.reason == "invalid"
    assert final.success is False
    assert final.reason == "max_attempts_exceeded"
    assert verification.attempt_count == 2


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_verify_signup_code_rejects_expired_code(unverified_user):
    verification = create_signup_verification(unverified_user)
    verification.expires_at = timezone.now() - timedelta(seconds=1)
    verification.save(update_fields=["expires_at"])
    code = extract_code_from_message(mail.outbox[-1].body)
    assert code is not None

    result = verify_signup_code(email=unverified_user.email, code=code)

    unverified_user.refresh_from_db()
    unverified_user.profile.refresh_from_db()

    assert result.success is False
    assert result.reason == "expired"
    assert unverified_user.is_active is False
    assert unverified_user.profile.email_verified_at is None


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS=60,
)
def test_resend_signup_code_honors_cooldown(unverified_user):
    baseline = len(getattr(mail, "outbox", []))
    create_signup_verification(unverified_user)

    result = resend_signup_code(email=unverified_user.email)

    assert result.success is False
    assert result.reason == "cooldown"
    assert result.retry_after_seconds is not None
    assert len(mail.outbox) == baseline + 1


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS=1,
)
def test_resend_signup_code_creates_new_code_after_cooldown(unverified_user):
    baseline = len(getattr(mail, "outbox", []))
    first = create_signup_verification(unverified_user)
    first.sent_at = timezone.now() - timedelta(minutes=5)
    first.save(update_fields=["sent_at"])

    result = resend_signup_code(email=unverified_user.email)
    first.refresh_from_db()
    pending_codes = EmailVerificationCode.objects.filter(
        user=unverified_user,
        consumed_at__isnull=True,
    )

    assert result.success is True
    assert result.reason == "sent"
    assert first.consumed_at is not None
    assert pending_codes.count() == 1
    assert len(mail.outbox) == baseline + 2


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS=1,
)
def test_resend_signup_code_invalidates_previous_code(unverified_user):
    first = create_signup_verification(unverified_user)
    first_code = extract_code_from_message(mail.outbox[-1].body)
    assert first_code is not None

    first.sent_at = timezone.now() - timedelta(minutes=5)
    first.save(update_fields=["sent_at"])

    resend_result = resend_signup_code(email=unverified_user.email)
    second_code = extract_code_from_message(mail.outbox[-1].body)
    assert second_code is not None

    old_code_result = verify_signup_code(email=unverified_user.email, code=first_code)
    new_code_result = verify_signup_code(email=unverified_user.email, code=second_code)

    assert resend_result.success is True
    assert old_code_result.success is False
    assert old_code_result.reason == "invalid"
    assert new_code_result.success is True
    assert new_code_result.reason == "verified"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_VERIFICATION_MAX_ATTEMPTS=2,
    EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS=1,
)
def test_resend_signup_code_recovers_after_max_attempts(unverified_user):
    create_signup_verification(unverified_user)
    first_code = EmailVerificationCode.objects.get(user=unverified_user)
    first_code.sent_at = timezone.now() - timedelta(minutes=5)
    first_code.save(update_fields=["sent_at"])

    verify_signup_code(email=unverified_user.email, code="000000")
    verify_signup_code(email=unverified_user.email, code="111111")

    resend_result = resend_signup_code(email=unverified_user.email)
    replacement_code = extract_code_from_message(mail.outbox[-1].body)
    assert replacement_code is not None

    verification_result = verify_signup_code(email=unverified_user.email, code=replacement_code)

    assert resend_result.success is True
    assert verification_result.success is True
    assert verification_result.reason == "verified"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_resend_signup_code_rejects_unknown_email():
    result = resend_signup_code(email="missing@example.com")

    assert result.success is False
    assert result.reason == "not_found"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_resend_signup_code_rejects_blank_email():
    result = resend_signup_code(email="")

    assert result.success is False
    assert result.reason == "invalid"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS=1,
)
def test_resend_signup_code_matches_email_case_insensitively(unverified_user):
    first = create_signup_verification(unverified_user)
    first.sent_at = timezone.now() - timedelta(minutes=5)
    first.save(update_fields=["sent_at"])

    result = resend_signup_code(email=unverified_user.email.upper())

    assert result.success is True
    assert result.reason == "sent"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_resend_signup_code_rejects_already_verified_user(unverified_user):
    unverified_user.is_active = True
    unverified_user.save(update_fields=["is_active"])
    unverified_user.profile.email_verified_at = timezone.now()
    unverified_user.profile.save(update_fields=["email_verified_at"])

    result = resend_signup_code(email=unverified_user.email)

    assert result.success is False
    assert result.reason == "already_verified"
