from datetime import timedelta
from io import StringIO
from uuid import uuid4

from apps.users.models import (
    EmailVerificationCode,
    EmailVerificationPurpose,
    UserProfile,
    UserRole,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.utils import timezone


def _make_unverified_user(*, age_days: int = 0):
    suffix = uuid4().hex[:8]
    user = get_user_model().objects.create_user(
        username=f"cleanup-user-{suffix}",
        email=f"cleanup-{suffix}@example.com",
        password="password123",
        is_active=False,
    )
    if age_days:
        user.date_joined = timezone.now() - timedelta(days=age_days)
        user.save(update_fields=["date_joined"])
    UserProfile.objects.create(user=user, role=UserRole.STUDENT)
    return user


def _make_code(*, user, expired: bool = False, consumed: bool = False):
    now = timezone.now()
    code = EmailVerificationCode.objects.create(
        user=user,
        email=user.email,
        purpose=EmailVerificationPurpose.SIGNUP,
        code_hash=make_password("123456"),
        expires_at=now - timedelta(minutes=1) if expired else now + timedelta(minutes=15),
    )
    if consumed:
        code.consumed_at = now - timedelta(seconds=5)
        code.save(update_fields=["consumed_at"])
    return code


def test_cleanup_email_verifications_removes_expired_and_consumed_codes():
    expired_user = _make_unverified_user()
    consumed_user = _make_unverified_user()
    active_user = _make_unverified_user()

    expired_code = _make_code(user=expired_user, expired=True)
    consumed_code = _make_code(user=consumed_user, consumed=True)
    active_code = _make_code(user=active_user)

    stdout = StringIO()
    call_command("cleanup_email_verifications", stdout=stdout)

    assert not EmailVerificationCode.objects.filter(pk=expired_code.pk).exists()
    assert not EmailVerificationCode.objects.filter(pk=consumed_code.pk).exists()
    assert EmailVerificationCode.objects.filter(pk=active_code.pk).exists()
    assert "Deleted email verification codes:" in stdout.getvalue()


def test_cleanup_email_verifications_optionally_deletes_stale_unverified_users():
    stale_user = _make_unverified_user(age_days=10)
    fresh_user = _make_unverified_user(age_days=1)
    verified_user = _make_unverified_user(age_days=10)
    verified_user.is_active = True
    verified_user.save(update_fields=["is_active"])
    verified_user.profile.email_verified_at = timezone.now()
    verified_user.profile.save(update_fields=["email_verified_at"])

    stdout = StringIO()
    call_command(
        "cleanup_email_verifications",
        "--delete-stale-users",
        "--stale-user-age-days=7",
        stdout=stdout,
    )

    User = get_user_model()
    assert not User.objects.filter(pk=stale_user.pk).exists()
    assert User.objects.filter(pk=fresh_user.pk).exists()
    assert User.objects.filter(pk=verified_user.pk).exists()
    assert "Deleted stale unverified users:" in stdout.getvalue()


def test_cleanup_email_verifications_keeps_stale_users_without_delete_flag():
    stale_user = _make_unverified_user(age_days=10)

    stdout = StringIO()
    call_command("cleanup_email_verifications", stdout=stdout)

    User = get_user_model()
    assert User.objects.filter(pk=stale_user.pk).exists()
    assert "Deleted stale unverified users" not in stdout.getvalue()


def test_cleanup_email_verifications_keeps_active_stale_users_even_with_delete_flag():
    active_stale_user = _make_unverified_user(age_days=10)
    active_stale_user.is_active = True
    active_stale_user.save(update_fields=["is_active"])

    stdout = StringIO()
    call_command(
        "cleanup_email_verifications",
        "--delete-stale-users",
        "--stale-user-age-days=7",
        stdout=stdout,
    )

    User = get_user_model()
    assert User.objects.filter(pk=active_stale_user.pk).exists()
    assert "Deleted stale unverified users:" in stdout.getvalue()
