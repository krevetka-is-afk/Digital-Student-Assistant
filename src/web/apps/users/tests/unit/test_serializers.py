from types import SimpleNamespace
from uuid import uuid4

from apps.users.models import UserProfile, UserRole
from apps.users.serializers import UserProfileSerializer
from django.contrib.auth import get_user_model


def _make_profile(*, is_staff: bool = False, role: str = UserRole.STUDENT):
    suffix = uuid4().hex[:8]
    user = get_user_model().objects.create_user(
        username=f"serializer-user-{suffix}",
        email=f"serializer-{suffix}@example.com",
        password="password123",
        is_staff=is_staff,
    )
    return UserProfile.objects.create(
        user=user,
        role=role,
        favorite_project_ids=[1, 2, 2],
    )


def test_user_profile_serializer_exposes_favorite_count_and_verification_state():
    profile = _make_profile()

    payload = UserProfileSerializer(profile).data

    assert payload["favorite_projects_count"] == 3
    assert payload["email_verified"] is False
    assert payload["email_verified_at"] is None


def test_user_profile_serializer_reports_zero_favorite_count_for_empty_list():
    profile = _make_profile()
    profile.favorite_project_ids = []

    payload = UserProfileSerializer(profile).data

    assert payload["favorite_projects_count"] == 0


def test_user_profile_serializer_reports_zero_favorite_count_for_none():
    profile = _make_profile()
    profile.favorite_project_ids = None

    payload = UserProfileSerializer(profile).data

    assert payload["favorite_projects_count"] == 0


def test_user_profile_serializer_keeps_role_read_only_for_non_staff_request():
    profile = _make_profile()
    serializer = UserProfileSerializer(
        profile,
        context={"request": SimpleNamespace(user=SimpleNamespace(is_staff=False))},
    )

    assert serializer.fields["role"].read_only is True


def test_user_profile_serializer_allows_role_edit_for_staff_request():
    profile = _make_profile(is_staff=True)
    serializer = UserProfileSerializer(
        profile,
        context={"request": SimpleNamespace(user=SimpleNamespace(is_staff=True))},
    )

    assert serializer.fields["role"].read_only is False


def test_user_profile_serializer_keeps_role_read_only_without_request_context():
    profile = _make_profile()
    serializer = UserProfileSerializer(profile)

    assert serializer.fields["role"].read_only is True


def test_user_profile_serializer_rejects_role_update_for_non_staff():
    profile = _make_profile()
    serializer = UserProfileSerializer(
        profile,
        data={"role": UserRole.CPPRP},
        partial=True,
        context={"request": SimpleNamespace(user=SimpleNamespace(is_staff=False))},
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {"role": ["You cannot change role via this endpoint."]}


def test_user_profile_serializer_allows_non_role_update_for_non_staff():
    profile = _make_profile()
    serializer = UserProfileSerializer(
        profile,
        data={"interests": ["python", "ml"]},
        partial=True,
        context={"request": SimpleNamespace(user=SimpleNamespace(is_staff=False))},
    )

    assert serializer.is_valid(), serializer.errors
