from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import EmailVerificationCode, EmailVerificationPurpose, UserProfile

User = get_user_model()

_CODE_PATTERN = re.compile(r"\b(\d{6})\b")

VERIFICATION_GENERIC_RESEND_MESSAGE = (
    "Если аккаунт ожидает подтверждения, мы отправим новый код на указанный email."
)


@dataclass(slots=True)
class VerificationResult:
    success: bool
    reason: str
    message: str
    user: Any | None = None

    @property
    def error_code(self) -> str:
        return self.reason


@dataclass(slots=True)
class ResendResult:
    success: bool
    reason: str
    message: str
    retry_after_seconds: int | None = None


def _code_ttl_seconds() -> int:
    return int(getattr(settings, "EMAIL_VERIFICATION_CODE_TTL_SECONDS", 900))


def _resend_cooldown_seconds() -> int:
    return int(getattr(settings, "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", 60))


def _max_attempts() -> int:
    return int(getattr(settings, "EMAIL_VERIFICATION_MAX_ATTEMPTS", 5))


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _verification_subject() -> str:
    return "Подтверждение email для Digital Student Assistant"


def _verification_message(*, code: str, ttl_seconds: int) -> str:
    ttl_minutes = max(1, ttl_seconds // 60)
    return (
        "Ваш код подтверждения email для Digital Student Assistant: "
        f"{code}\n\nКод действует {ttl_minutes} мин."
    )


def extract_code_from_message(message: str) -> str | None:
    match = _CODE_PATTERN.search(message or "")
    if match is None:
        return None
    return match.group(1)


def _pending_signup_codes(user):
    return EmailVerificationCode.objects.filter(
        user=user,
        purpose=EmailVerificationPurpose.SIGNUP,
        consumed_at__isnull=True,
    )


def is_user_pending_email_verification(user) -> bool:
    if user is None or getattr(user, "is_active", True):
        return False
    try:
        profile = user.profile
    except ObjectDoesNotExist:
        return True
    return profile.email_verified_at is None


def pending_email_verification_user_for_credentials(identifier: str, password: str):
    normalized_identifier = (identifier or "").strip()
    if not normalized_identifier or not password:
        return None

    user = (
        User.objects.select_related("profile")
        .filter(email__iexact=normalized_identifier)
        .first()
    )
    if user is None:
        user = User.objects.select_related("profile").filter(username=normalized_identifier).first()
    if user is None or not is_user_pending_email_verification(user):
        return None
    if not user.check_password(password):
        return None
    return user


def create_signup_verification(user) -> EmailVerificationCode:
    now = timezone.now()
    ttl_seconds = _code_ttl_seconds()
    code = _generate_code()

    with transaction.atomic():
        _pending_signup_codes(user).update(consumed_at=now)
        verification = EmailVerificationCode.objects.create(
            user=user,
            email=(user.email or "").strip().lower(),
            purpose=EmailVerificationPurpose.SIGNUP,
            code_hash=make_password(code),
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

    send_mail(
        subject=_verification_subject(),
        message=_verification_message(code=code, ttl_seconds=ttl_seconds),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@localhost"),
        recipient_list=[user.email],
    )
    return verification


def verify_signup_code(*, email: str, code: str) -> VerificationResult:
    normalized_email = (email or "").strip().lower()
    normalized_code = (code or "").strip()
    if not normalized_email or not normalized_code:
        return VerificationResult(
            success=False,
            reason="missing_fields",
            message="Введите email и код подтверждения.",
        )

    with transaction.atomic():
        verification = (
            EmailVerificationCode.objects.select_for_update()
            .select_related("user")
            .filter(
                email=normalized_email,
                purpose=EmailVerificationPurpose.SIGNUP,
                consumed_at__isnull=True,
            )
            .order_by("-sent_at")
            .first()
        )
        if verification is None:
            return VerificationResult(
                success=False,
                reason="invalid",
                message="Неверный код подтверждения.",
            )
        if verification.attempt_count >= _max_attempts():
            return VerificationResult(
                success=False,
                reason="max_attempts_exceeded",
                message="Превышено количество попыток. Запросите новый код.",
            )
        if verification.is_expired:
            return VerificationResult(
                success=False,
                reason="expired",
                message="Срок действия кода истёк. Запросите новый код.",
            )
        if not check_password(normalized_code, verification.code_hash):
            verification.attempt_count += 1
            verification.save(update_fields=["attempt_count"])
            return VerificationResult(
                success=False,
                reason="invalid",
                message="Неверный код подтверждения.",
            )

        user = verification.user
        profile, _ = UserProfile.objects.select_for_update().get_or_create(user=user)
        verified_at = timezone.now()
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        profile.mark_email_verified(verified_at=verified_at)
        profile.save(update_fields=["email_verified_at"])

        verification.consumed_at = verified_at
        verification.save(update_fields=["consumed_at"])
        _pending_signup_codes(user).exclude(pk=verification.pk).update(consumed_at=verified_at)

    return VerificationResult(
        success=True,
        reason="verified",
        message="Email подтверждён.",
        user=user,
    )


def resend_signup_code(email: str) -> ResendResult:
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return ResendResult(
            success=False,
            reason="invalid",
            message=VERIFICATION_GENERIC_RESEND_MESSAGE,
        )

    user = User.objects.filter(email__iexact=normalized_email).first()
    if user is None:
        return ResendResult(
            success=False,
            reason="not_found",
            message=VERIFICATION_GENERIC_RESEND_MESSAGE,
        )

    profile, _ = UserProfile.objects.get_or_create(user=user)
    if profile.email_verified:
        return ResendResult(
            success=False,
            reason="already_verified",
            message=VERIFICATION_GENERIC_RESEND_MESSAGE,
        )

    latest_code = (
        EmailVerificationCode.objects.filter(
            user=user,
            purpose=EmailVerificationPurpose.SIGNUP,
        )
        .order_by("-sent_at")
        .first()
    )
    if latest_code is not None:
        retry_after = _resend_cooldown_seconds() - int(
            (timezone.now() - latest_code.sent_at).total_seconds()
        )
        if retry_after > 0:
            return ResendResult(
                success=False,
                reason="cooldown",
                message="Код уже был отправлен недавно.",
                retry_after_seconds=retry_after,
            )

    create_signup_verification(user)
    return ResendResult(success=True, reason="sent", message=VERIFICATION_GENERIC_RESEND_MESSAGE)
