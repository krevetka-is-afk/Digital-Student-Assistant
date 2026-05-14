from uuid import uuid4

from apps.users.email_verification import extract_code_from_message
from apps.users.models import (
    EmailVerificationCode,
    ExternalAccessAllowlist,
    ExternalAccessRequest,
    ExternalAccessRequestStatus,
    UserRole,
)
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_register_api_creates_unverified_student_and_sends_code():
    email = f"api-student-{uuid4().hex[:8]}@edu.hse.ru"

    response = Client().post(
        reverse("api-v1-auth-register"),
        data={
            "email": email,
            "password": "password123",
            "name": "API Student",
            "role": UserRole.STUDENT,
            "personal_data_consent": True,
        },
        content_type="application/json",
    )

    user = User.objects.get(email=email)
    assert response.status_code == 201
    assert response.json()["status"] == "verification_sent"
    assert response.json()["email"] == email
    assert response.json()["username"] == user.username
    assert response.json()["email_verification_required"] is True
    assert user.is_active is False
    assert user.profile.role == UserRole.STUDENT
    assert EmailVerificationCode.objects.filter(user=user, consumed_at__isnull=True).exists()
    assert len(mail.outbox) == 1


def test_register_api_rejects_non_corporate_student_email():
    email = f"api-student-{uuid4().hex[:8]}@gmail.com"

    response = Client().post(
        reverse("api-v1-auth-register"),
        data={
            "email": email,
            "password": "password123",
            "name": "API Student",
            "role": UserRole.STUDENT,
            "personal_data_consent": True,
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "email" in response.json()
    assert not User.objects.filter(email=email).exists()


def test_register_api_creates_external_customer_access_request():
    email = f"api-customer-{uuid4().hex[:8]}@example.com"

    response = Client().post(
        reverse("api-v1-auth-register"),
        data={
            "email": email,
            "password": "password123",
            "name": "API Customer",
            "role": UserRole.CUSTOMER,
            "personal_data_consent": True,
        },
        content_type="application/json",
    )

    assert response.status_code == 202
    assert response.json()["status"] == "access_request_created"
    assert ExternalAccessRequest.objects.filter(email=email).exists()
    assert (
        ExternalAccessRequest.objects.get(email=email).status
        == ExternalAccessRequestStatus.PENDING
    )
    assert not User.objects.filter(email=email).exists()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_register_api_creates_allowlisted_external_customer():
    email = f"api-allowlisted-{uuid4().hex[:8]}@example.com"
    ExternalAccessAllowlist.objects.create(email=email, allowed_role=UserRole.CUSTOMER)

    response = Client().post(
        reverse("api-v1-auth-register"),
        data={
            "email": email,
            "password": "password123",
            "name": "API Customer",
            "role": UserRole.CUSTOMER,
            "personal_data_consent": True,
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "verification_sent"
    assert User.objects.filter(email=email).exists()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_verify_email_api_activates_user_after_registration():
    email = f"api-verify-{uuid4().hex[:8]}@edu.hse.ru"
    client = Client()
    register_response = client.post(
        reverse("api-v1-auth-register"),
        data={
            "email": email,
            "password": "password123",
            "name": "API Verify",
            "role": UserRole.STUDENT,
            "personal_data_consent": True,
        },
        content_type="application/json",
    )

    assert register_response.status_code == 201
    code = extract_code_from_message(mail.outbox[-1].body)
    assert code is not None

    verify_response = client.post(
        reverse("api-v1-auth-verify-email"),
        data={"email": email, "code": code},
        content_type="application/json",
    )

    user = User.objects.get(email=email)
    user.refresh_from_db()
    user.profile.refresh_from_db()
    assert verify_response.status_code == 200
    assert verify_response.json()["status"] == "verified"
    assert verify_response.json()["email_verified"] is True
    assert user.is_active is True
    assert user.profile.email_verified_at is not None


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_resend_verification_api_returns_cooldown_when_requested_too_soon():
    email = f"api-resend-{uuid4().hex[:8]}@edu.hse.ru"
    client = Client()
    register_response = client.post(
        reverse("api-v1-auth-register"),
        data={
            "email": email,
            "password": "password123",
            "name": "API Resend",
            "role": UserRole.STUDENT,
            "personal_data_consent": True,
        },
        content_type="application/json",
    )

    assert register_response.status_code == 201
    resend_response = client.post(
        reverse("api-v1-auth-verify-email-resend"),
        data={"email": email},
        content_type="application/json",
    )

    assert resend_response.status_code == 429
    assert resend_response.json()["status"] == "cooldown"
    assert resend_response.json()["retry_after_seconds"] > 0
