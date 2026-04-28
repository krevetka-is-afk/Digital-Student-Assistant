"""
Role-based access control decorators for SSR frontend views.

Usage
-----
    from apps.frontend.decorators import customer_required, student_required, moderator_required

    @customer_required
    def project_create(request): ...

    @student_required
    def initiative_project_create(request): ...

    @moderator_required
    def moderation_list(request): ...
"""

import functools

from apps.users.models import UserRole
from apps.users.utils import user_is_moderator
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def _get_role(user) -> str:
    """Return the user's role string, or '' if profile is missing."""
    try:
        return user.profile.role
    except Exception:
        return ""


def require_role(*roles: str, redirect_url: str = "frontend:project_list", message: str = ""):
    """
    Decorator factory that restricts a view to users with one of the given roles.

    On failure redirects to *redirect_url* with an optional flash message.
    If the user is not authenticated, the login_required decorator (applied
    separately on the view) handles the redirect to /auth/.
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if _get_role(request.user) not in roles:
                if message:
                    messages.error(request, message)
                return redirect(redirect_url)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def moderator_required(view_func):
    """
    Restrict a view to CPPRP moderators and Django staff.

    Raises PermissionDenied (→ 403) so the browser shows an error page rather
    than silently redirecting; this makes access violations clearly visible.
    """

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_staff or user_is_moderator(request.user)):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper


# Convenience shorthands -------------------------------------------------

customer_required = require_role(
    UserRole.CUSTOMER,
    message="Создавать проекты могут только заказчики.",
)

student_required = require_role(
    UserRole.STUDENT,
    message="Инициативные проекты могут предлагать только студенты.",
)
