import functools

from apps.users.models import UserRole
from apps.users.utils import user_is_moderator
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def _get_role(user) -> str:
    try:
        return user.profile.role
    except Exception:
        return ""


def require_role(*roles: str, redirect_url: str = "frontend:project_list", message: str = ""):

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

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_staff or user_is_moderator(request.user)):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper


customer_required = require_role(
    UserRole.CUSTOMER,
    message="Создавать проекты могут только заказчики.",
)

student_required = require_role(
    UserRole.STUDENT,
    message="Инициативные проекты могут предлагать только студенты.",
)
