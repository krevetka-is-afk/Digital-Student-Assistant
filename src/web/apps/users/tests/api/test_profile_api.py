from uuid import uuid4

from apps.projects.models import Project, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone


def _make_user(*, role: str = UserRole.STUDENT, is_staff: bool = False):
    username = f"user-{uuid4().hex[:8]}"
    user = get_user_model().objects.create_user(
        username=username,
        password="placeholder",
        is_staff=is_staff,
        email=f"{username}@example.com",
    )
    UserProfile.objects.create(user=user, role=role)
    return user


def test_non_staff_cannot_change_own_role_via_me_endpoint():
    user = _make_user(role=UserRole.STUDENT)
    client = Client()
    client.force_login(user)

    response = client.patch(
        reverse("user-profile-me"),
        data={"role": UserRole.CPPRP},
        content_type="application/json",
    )

    user.profile.refresh_from_db()
    assert response.status_code == 400
    assert response.json() == {"role": ["You cannot change role via this endpoint."]}
    assert user.profile.role == UserRole.STUDENT


def test_cpprp_endpoint_stays_forbidden_after_failed_role_escalation():
    user = _make_user(role=UserRole.STUDENT)
    client = Client()
    client.force_login(user)

    update_response = client.patch(
        reverse("user-profile-me"),
        data={"role": UserRole.CPPRP},
        content_type="application/json",
    )
    queue_response = client.get(reverse("account-cpprp-moderation-queue"))

    assert update_response.status_code == 400
    assert queue_response.status_code == 403


def test_non_staff_cannot_change_own_role_via_put_me_endpoint():
    user = _make_user(role=UserRole.STUDENT)
    client = Client()
    client.force_login(user)

    response = client.put(
        reverse("user-profile-me"),
        data={"role": UserRole.CPPRP},
        content_type="application/json",
    )

    user.profile.refresh_from_db()
    assert response.status_code == 400
    assert response.json() == {"role": ["You cannot change role via this endpoint."]}
    assert user.profile.role == UserRole.STUDENT


def test_staff_can_change_own_role_via_me_endpoint():
    staff = _make_user(role=UserRole.STUDENT, is_staff=True)
    client = Client()
    client.force_login(staff)

    response = client.patch(
        reverse("user-profile-me"),
        data={"role": UserRole.CPPRP},
        content_type="application/json",
    )

    staff.profile.refresh_from_db()
    assert response.status_code == 200
    assert response.json()["role"] == UserRole.CPPRP
    assert staff.profile.role == UserRole.CPPRP


def test_profile_me_exposes_email_verification_status():
    user = _make_user(role=UserRole.STUDENT)
    user.profile.email_verified_at = timezone.now()
    user.profile.save(update_fields=["email_verified_at"])

    client = Client()
    client.force_login(user)

    response = client.get(reverse("user-profile-me"))

    assert response.status_code == 200
    assert response.json()["email_verified"] is True
    assert response.json()["email_verified_at"] is not None


def test_user_cannot_set_email_verification_fields_via_me_endpoint():
    user = _make_user(role=UserRole.STUDENT)
    client = Client()
    client.force_login(user)

    response = client.patch(
        reverse("user-profile-me"),
        data={
            "email_verified": True,
            "email_verified_at": "2026-04-25T12:00:00Z",
            "interests": ["safe-update"],
        },
        content_type="application/json",
    )

    user.profile.refresh_from_db()
    assert response.status_code == 200
    assert response.json()["email_verified"] is False
    assert response.json()["email_verified_at"] is None
    assert user.profile.email_verified_at is None
    assert user.profile.interests == ["safe-update"]


def test_user_can_update_interests_and_favorite_project_ids_via_me_endpoint():
    user = _make_user(role=UserRole.STUDENT)
    project = Project.objects.create(title="Saved project", status=ProjectStatus.PUBLISHED)
    client = Client()
    client.force_login(user)

    response = client.patch(
        reverse("user-profile-me"),
        data={"interests": ["python", "ml"], "favorite_project_ids": [project.pk]},
        content_type="application/json",
    )

    user.profile.refresh_from_db()
    assert response.status_code == 200
    assert response.json()["interests"] == ["python", "ml"]
    assert response.json()["favorite_project_ids"] == [project.pk]
    assert user.profile.interests == ["python", "ml"]
    assert user.profile.favorite_project_ids == [project.pk]


def test_user_can_manage_favorite_projects():
    user = _make_user()
    project = Project.objects.create(title="Favorite me", status=ProjectStatus.PUBLISHED)

    client = Client()
    client.force_login(user)

    add_response = client.post(
        reverse("user-profile-favorites"),
        data={"project_id": project.pk},
        content_type="application/json",
    )

    assert add_response.status_code == 200
    assert add_response.json()["project_ids"] == [project.pk]

    delete_response = client.delete(
        reverse("user-profile-favorite-detail", kwargs={"pk": project.pk}),
    )

    assert delete_response.status_code == 204
