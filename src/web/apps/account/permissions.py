import logging

from apps.users.models import UserRole
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


def get_user_role(user) -> str | None:
    if not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "is_service", False):
        return f"service:{getattr(user, 'service_name', 'unknown')}"
    if getattr(user, "is_staff", False):
        return "staff"
    try:
        return user.profile.role
    except ObjectDoesNotExist:
        return None


def has_any_role(user, *, allowed: set[str], allow_staff: bool = True) -> bool:
    role = get_user_role(user)
    if allow_staff and role == "staff":
        return True
    return role in allowed


def require_roles(user, *, allowed: set[str]) -> str:
    role = get_user_role(user)
    if has_any_role(user, allowed=allowed):
        return role or "staff"
    raise PermissionDenied("You do not have access to this account endpoint.")


def is_student(user) -> bool:
    return get_user_role(user) == UserRole.STUDENT


def is_customer(user) -> bool:
    return get_user_role(user) == UserRole.CUSTOMER


def is_cpprp(user) -> bool:
    return get_user_role(user) == UserRole.CPPRP


def _log_denied_access(request, view) -> None:
    user = getattr(request, "user", None)
    logger.warning(
        "Denied API access: method=%s path=%s view=%s user_id=%s role=%s",
        request.method,
        request.path,
        view.__class__.__name__,
        getattr(user, "id", None),
        get_user_role(user),
    )


class RolePermission(permissions.BasePermission):
    allowed_roles: set[str] = set()
    message = "You do not have permission to perform this action."
    log_denied = False

    def has_permission(self, request, view) -> bool:
        allowed = has_any_role(request.user, allowed=self.allowed_roles)
        if not allowed and self.log_denied:
            _log_denied_access(request, view)
        return allowed


class IsStudentOrStaff(RolePermission):
    allowed_roles = {UserRole.STUDENT}
    message = "Only students or staff can access this endpoint."


class IsCustomerOrStaff(RolePermission):
    allowed_roles = {UserRole.CUSTOMER}
    message = "Only customers or staff can access this endpoint."


class IsCpprpOrStaff(RolePermission):
    allowed_roles = {UserRole.CPPRP}
    message = "Only CPPRP or staff can access this endpoint."
    log_denied = True


class ServicePermission(permissions.BasePermission):
    message = "Only authenticated service principals can access this endpoint."
    log_denied = False

    def has_permission(self, request, view) -> bool:
        allowed = getattr(getattr(request, "user", None), "is_service", False)
        if not allowed and self.log_denied:
            _log_denied_access(request, view)
        return allowed


class IsConfiguredOutboxConsumerService(ServicePermission):
    message = "Only configured outbox consumer services can access this endpoint."
    log_denied = True

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        configured = getattr(settings, "OUTBOX_SERVICE_TOKENS", {}) or {}
        allowed = getattr(request.user, "service_name", "") in configured
        if not allowed and self.log_denied:
            _log_denied_access(request, view)
        return allowed


class AnyPermission(permissions.BasePermission):
    permission_classes: tuple[type[permissions.BasePermission], ...] = ()
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        for permission_class in self.permission_classes:
            if permission_class().has_permission(request, view):
                return True
        return False


class IsOutboxConsumerOrCpprpOrStaff(AnyPermission):
    permission_classes = (IsCpprpOrStaff, IsConfiguredOutboxConsumerService)
    message = "Only CPPRP, staff, or configured outbox consumer services can access this endpoint."
