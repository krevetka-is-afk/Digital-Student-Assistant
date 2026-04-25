from datetime import timedelta

from apps.users.models import EmailVerificationCode, UserProfile, UserRole
from django.utils import timezone


def test_user_profile_defaults():
    profile = UserProfile()

    assert profile.role == UserRole.STUDENT
    assert profile.interests == []
    assert profile.favorite_project_ids == []
    assert profile.email_verified_at is None


def test_user_profile_mark_email_verified_sets_timestamp():
    profile = UserProfile()

    profile.mark_email_verified()

    assert profile.is_email_verified is True
    assert profile.email_verified_at is not None


def test_user_profile_mark_email_verified_accepts_explicit_timestamp():
    profile = UserProfile()
    explicit_time = timezone.now() - timedelta(days=1)

    profile.mark_email_verified(verified_at=explicit_time)

    assert profile.email_verified_at == explicit_time


def test_email_verification_code_flags_reflect_state():
    now = timezone.now()
    expired_code = EmailVerificationCode(expires_at=now - timedelta(seconds=1))
    active_code = EmailVerificationCode(expires_at=now + timedelta(minutes=5))
    consumed_code = EmailVerificationCode(
        expires_at=now + timedelta(minutes=5),
        consumed_at=now,
    )

    assert expired_code.is_expired is True
    assert active_code.is_expired is False
    assert active_code.is_consumed is False
    assert consumed_code.is_consumed is True


def test_set_favorite_project_ids_normalizes_and_deduplicates_values():
    profile = UserProfile()

    profile.set_favorite_project_ids([1, 2, 1, 3, 3])

    assert profile.favorite_project_ids == [1, 2, 3]
