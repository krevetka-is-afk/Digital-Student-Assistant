from apps.users.models import UserRole
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import PermissionDenied


def get_user_role(user) -> str | None:
    if not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "is_staff", False):
        return "staff"
    try:
        return user.profile.role
    except ObjectDoesNotExist:
        return None


def require_roles(user, *, allowed: set[str]) -> str:
    role = get_user_role(user)
    if role == "staff" or role in allowed:
        return role or "staff"
    raise PermissionDenied("You do not have access to this account endpoint.")


def is_student(user) -> bool:
    return get_user_role(user) == UserRole.STUDENT


def is_customer(user) -> bool:
    return get_user_role(user) == UserRole.CUSTOMER


def is_cpprp(user) -> bool:
    return get_user_role(user) == UserRole.CPPRP
