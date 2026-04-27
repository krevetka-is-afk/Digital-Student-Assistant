from uuid import uuid4

from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone


def _make_user(*, email: str, is_active: bool, verified: bool):
    suffix = uuid4().hex[:8]
    user = get_user_model().objects.create_user(
        username=f"{email.split('@')[0]}-{suffix}",
        email=email,
        password="password123",
        is_active=is_active,
    )
    UserProfile.objects.create(
        user=user,
        role=UserRole.STUDENT,
        email_verified_at=timezone.now() if verified else None,
    )
    return user


def test_api_v1_token_rejects_unverified_user_with_specific_code():
    user = _make_user(
        email=f"pending-token-{uuid4().hex[:8]}@example.com",
        is_active=False,
        verified=False,
    )

    response = Client().post(
        reverse("api-v1-auth-token"),
        data={"username": user.username, "password": "password123"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"


def test_api_v1_token_issues_token_for_verified_user():
    user = _make_user(
        email=f"verified-token-{uuid4().hex[:8]}@example.com",
        is_active=True,
        verified=True,
    )

    response = Client().post(
        reverse("api-v1-auth-token"),
        data={"username": user.username, "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["token"]


def test_legacy_base_token_rejects_unverified_user():
    user = _make_user(
        email=f"legacy-pending-{uuid4().hex[:8]}@example.com",
        is_active=False,
        verified=False,
    )

    response = Client().post(
        "/base/auth/",
        data={"username": user.username, "password": "password123"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"
