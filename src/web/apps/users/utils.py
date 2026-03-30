from apps.users.models import UserRole


def user_is_moderator(user) -> bool:
    """Returns True if the user has the CPPRP (moderator) role."""
    if not getattr(user, "is_authenticated", False):
        return False
    try:
        return user.profile.role == UserRole.CPPRP
    except Exception:
        return False
