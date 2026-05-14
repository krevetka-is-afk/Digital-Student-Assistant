from __future__ import annotations

from dataclasses import dataclass, field

from apps.users.email_verification import create_signup_verification
from apps.users.models import (
    ExternalAccessAllowlist,
    ExternalAccessRequest,
    ExternalAccessRequestStatus,
    UserProfile,
    UserRole,
    normalize_email,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as validate_email_format
from django.db import transaction

User = get_user_model()

NAME_MAX = 100
PASSWORD_MIN = 8


@dataclass(slots=True)
class RegistrationResult:
    success: bool
    status: str
    message: str
    field_errors: dict[str, list[str]] = field(default_factory=dict)
    user: User | None = None
    normalized_email: str = ""
    username: str = ""
    role: str = ""


def check_email_format(email: str) -> bool:
    try:
        validate_email_format(email)
        return True
    except ValidationError:
        return False


def email_domain(email: str) -> str:
    normalized = normalize_email(email)
    _, _, domain = normalized.partition("@")
    return domain


def is_corporate_email(email: str) -> bool:
    domain = email_domain(email)
    return bool(domain) and domain in {
        item.strip().lower() for item in getattr(settings, "ALLOWED_CORPORATE_EMAIL_DOMAINS", [])
    }


def external_email_is_allowlisted(email: str, role: str) -> bool:
    normalized = normalize_email(email)
    return ExternalAccessAllowlist.objects.filter(
        email=normalized,
        allowed_role=role,
        is_active=True,
    ).exists()


def create_or_refresh_external_access_request(
    *,
    email: str,
    full_name: str,
    requested_role: str,
) -> None:
    normalized = normalize_email(email)
    request_obj = ExternalAccessRequest.objects.filter(email=normalized).first()
    if request_obj is None:
        ExternalAccessRequest.objects.create(
            email=normalized,
            full_name=full_name,
            requested_role=requested_role,
        )
        return

    request_obj.full_name = full_name
    request_obj.requested_role = requested_role
    request_obj.status = ExternalAccessRequestStatus.PENDING
    request_obj.decision_note = ""
    request_obj.reviewed_by = None
    request_obj.reviewed_at = None
    request_obj.save(
        update_fields=[
            "full_name",
            "requested_role",
            "status",
            "decision_note",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ]
    )


def build_unique_username(email: str) -> str:
    base = email.split("@")[0]
    username, suffix = base, 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{suffix}"
        suffix += 1
    return username


def register_user(
    *,
    email: str,
    password: str,
    full_name: str,
    role: str,
    personal_data_consent: bool,
) -> RegistrationResult:
    normalized_email = normalize_email(email)
    normalized_name = (full_name or "").strip()
    normalized_role = role if role in {UserRole.STUDENT, UserRole.CUSTOMER} else UserRole.STUDENT
    field_errors: dict[str, list[str]] = {}

    if not normalized_email:
        field_errors["email"] = ["Введите email."]
    elif not check_email_format(normalized_email):
        field_errors["email"] = ["Введите корректный email-адрес."]

    if not password:
        field_errors["password"] = ["Введите пароль."]
    elif len(password) < PASSWORD_MIN:
        field_errors["password"] = [
            f"Пароль должен содержать не менее {PASSWORD_MIN} символов."
        ]

    if normalized_name and len(normalized_name) > NAME_MAX:
        field_errors["name"] = [f"Имя не может превышать {NAME_MAX} символов."]

    if not personal_data_consent:
        field_errors["personal_data_consent"] = [
            "Для регистрации необходимо согласие на обработку персональных данных."
        ]

    corporate_email = is_corporate_email(normalized_email)
    if (
        normalized_role == UserRole.STUDENT
        and normalized_email
        and "email" not in field_errors
        and not corporate_email
    ):
        field_errors["email"] = [
            "Автоматическая регистрация на сервис \
                доступна только для корпоративных адресов НИУ ВШЭ.\
                    Остальные адреса требуют одобрения сотрудником ЦППРП."
        ]

    if field_errors:
        return RegistrationResult(
            success=False,
            status="validation_error",
            message="Проверьте корректность данных.",
            field_errors=field_errors,
            normalized_email=normalized_email,
            role=normalized_role,
        )

    external_customer_needs_moderation = (
        normalized_role == UserRole.CUSTOMER
        and normalized_email
        and not corporate_email
        and not external_email_is_allowlisted(normalized_email, normalized_role)
    )
    if external_customer_needs_moderation:
        create_or_refresh_external_access_request(
            email=normalized_email,
            full_name=normalized_name,
            requested_role=normalized_role,
        )
        return RegistrationResult(
            success=True,
            status="access_request_created",
            message=(
                "Заявка на внешний доступ отправлена. После одобрения сотрудником ЦППРП "
                "вы сможете завершить регистрацию с этой почтой."
            ),
            normalized_email=normalized_email,
            role=normalized_role,
        )

    if User.objects.filter(email__iexact=normalized_email).exists():
        return RegistrationResult(
            success=False,
            status="duplicate_email",
            message="Пользователь с таким email уже существует.",
            field_errors={"email": ["Пользователь с таким email уже существует."]},
            normalized_email=normalized_email,
            role=normalized_role,
        )

    with transaction.atomic():
        new_user = User.objects.create_user(
            username=build_unique_username(normalized_email),
            email=normalized_email,
            password=password,
            is_active=False,
        )
        parts = normalized_name.split(" ", 1)
        new_user.first_name = parts[0] if parts else ""
        new_user.last_name = parts[1] if len(parts) > 1 else ""
        new_user.save(update_fields=["first_name", "last_name"])

        UserProfile.objects.create(user=new_user, role=normalized_role)
        create_signup_verification(new_user)

    return RegistrationResult(
        success=True,
        status="verification_sent",
        message="Мы отправили код подтверждения на указанный email.",
        user=new_user,
        normalized_email=normalized_email,
        username=new_user.username,
        role=normalized_role,
    )
