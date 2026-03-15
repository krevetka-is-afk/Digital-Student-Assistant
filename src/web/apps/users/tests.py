from apps.users.models import UserProfile, UserRole


def test_user_profile_defaults():
    profile = UserProfile()

    assert profile.role == UserRole.STUDENT
    assert profile.interests == []
