from urllib.parse import urlencode, urlsplit

from apps.users.email_verification import (
    VERIFICATION_GENERIC_RESEND_MESSAGE,
    create_signup_verification,
    is_user_pending_email_verification,
    resend_signup_code,
    verify_signup_code,
)
from apps.users.models import UserProfile, UserRole
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
)
from django.contrib.auth import (
    login as auth_login,
)
from django.contrib.auth import (
    logout as auth_logout,
)
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as _validate_email_fmt
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

_NAME_MAX = 100
_PASSWORD_MIN = 8


def _check_email_fmt(email: str) -> bool:
    try:
        _validate_email_fmt(email)
        return True
    except ValidationError:
        return False


def _safe_redirect_target(request, raw_next_url: str) -> str:
    candidate = (raw_next_url or "").strip()
    if not candidate:
        return reverse("frontend:project_list")

    # Resolve user-provided "next" only to server allowlisted internal routes.
    path = urlsplit(candidate).path
    allowed_paths_to_names = {
        reverse("frontend:project_list"): "frontend:project_list",
        reverse("frontend:auth"): "frontend:auth",
    }

    route_name = allowed_paths_to_names.get(path)
    if route_name:
        return reverse(route_name)

    return reverse("frontend:project_list")


def _build_unique_username(email: str) -> str:
    User = get_user_model()
    base = email.split("@")[0]
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{n}"
        n += 1
    return username


def _verification_redirect_url(email: str, next_url: str = "") -> str:
    query = {"email": email}
    if next_url:
        query["next"] = next_url
    return f"{reverse('frontend:verify_email')}?{urlencode(query)}"


def auth_view(request):
    """Combined login / register page. Redirects to project_list if already authenticated."""
    if request.user.is_authenticated:
        return redirect("frontend:project_list")

    next_url = request.GET.get("next", "").strip()
    active_tab = request.POST.get("tab", "login")
    login_errors: dict = {}
    register_errors: dict = {}

    # Saved POST values to re-fill form on error
    login_email = ""
    reg_email = ""
    reg_name = ""
    reg_role = UserRole.STUDENT
    login_requires_email_verification = False

    if request.method == "POST":
        next_url = request.POST.get("next", next_url).strip()

        # ── LOGIN ──────────────────────────────────────────────────────────
        if active_tab == "login":
            login_email = request.POST.get("email", "").strip()
            password = request.POST.get("password", "")

            if not login_email:
                login_errors["email"] = "Введите email."
            elif not _check_email_fmt(login_email):
                login_errors["email"] = "Введите корректный email-адрес."
            if not password:
                login_errors["password"] = "Введите пароль."

            if not login_errors:
                User = get_user_model()
                user_obj = None
                try:
                    user_obj = User.objects.get(email__iexact=login_email)
                    user = authenticate(request, username=user_obj.username, password=password)
                except User.DoesNotExist:
                    user = None

                if user is not None:
                    auth_login(request, user)
                    safe_next = _safe_redirect_target(request, next_url)
                    return redirect(safe_next)
                else:
                    if (
                        user_obj is not None
                        and is_user_pending_email_verification(user_obj)
                        and user_obj.check_password(password)
                    ):
                        login_requires_email_verification = True
                        login_errors["general"] = "Подтвердите email, чтобы войти."
                    else:
                        login_errors["general"] = "Неверный email или пароль."

        # ── REGISTER ───────────────────────────────────────────────────────
        elif active_tab == "register":
            reg_email = request.POST.get("email", "").strip().lower()
            password = request.POST.get("password", "")
            reg_name = request.POST.get("name", "").strip()
            reg_role = request.POST.get("role", UserRole.STUDENT)

            if not reg_email:
                register_errors["email"] = "Введите email."
            elif not _check_email_fmt(reg_email):
                register_errors["email"] = "Введите корректный email-адрес."
            if not password:
                register_errors["password"] = "Введите пароль."
            elif len(password) < _PASSWORD_MIN:
                register_errors["password"] = (
                    f"Пароль должен содержать не менее {_PASSWORD_MIN} символов."
                )
            if reg_name and len(reg_name) > _NAME_MAX:
                register_errors["name"] = f"Имя не может превышать {_NAME_MAX} символов."
            if reg_role not in {UserRole.STUDENT, UserRole.CUSTOMER}:
                reg_role = UserRole.STUDENT

            if not register_errors:
                User = get_user_model()
                if User.objects.filter(email__iexact=reg_email).exists():
                    register_errors["email"] = "Пользователь с таким email уже существует."
                else:
                    with transaction.atomic():
                        new_user = User.objects.create_user(
                            username=_build_unique_username(reg_email),
                            email=reg_email,
                            password=password,
                            is_active=False,
                        )
                        parts = reg_name.split(" ", 1)
                        new_user.first_name = parts[0]
                        new_user.last_name = parts[1] if len(parts) > 1 else ""
                        new_user.save(update_fields=["first_name", "last_name"])

                        UserProfile.objects.create(user=new_user, role=reg_role)
                        create_signup_verification(new_user)

                    messages.success(
                        request,
                        "Мы отправили код подтверждения на указанный email.",
                    )
                    return redirect(_verification_redirect_url(reg_email, next_url))

    return render(
        request,
        "frontend/auth.html",
        {
            "active_tab": active_tab,
            "next": next_url,
            "login_errors": login_errors,
            "register_errors": register_errors,
            "login_requires_email_verification": login_requires_email_verification,
            "login_email": login_email,
            "reg_email": reg_email,
            "reg_name": reg_name,
            "reg_role": reg_role,
            "UserRole": UserRole,
        },
    )


def verify_email_view(request):
    if request.user.is_authenticated:
        return redirect("frontend:project_list")

    next_url = request.GET.get("next", "").strip()
    email = request.GET.get("email", "").strip().lower()
    code = ""
    errors: dict[str, str] = {}

    if request.method == "POST":
        email = request.POST.get("email", email).strip().lower()
        code = request.POST.get("code", "").strip()
        next_url = request.POST.get("next", next_url).strip()

        result = verify_signup_code(email=email, code=code)
        if result.success and result.user is not None:
            auth_login(request, result.user)
            messages.success(request, f"Добро пожаловать, {result.user.username}!")
            return redirect(_safe_redirect_target(request, next_url))

        if result.error_code == "missing_fields":
            if not email:
                errors["email"] = "Введите email."
            if not code:
                errors["code"] = "Введите код подтверждения."
        errors["general"] = result.message

    return render(
        request,
        "frontend/verify_email.html",
        {
            "email": email,
            "code": code,
            "next": next_url,
            "errors": errors,
            "generic_resend_message": VERIFICATION_GENERIC_RESEND_MESSAGE,
        },
    )


@require_POST
def resend_email_code_view(request):
    email = request.POST.get("email", "").strip().lower()
    next_url = request.POST.get("next", "").strip()

    result = resend_signup_code(email)
    if result.retry_after_seconds:
        messages.info(
            request,
            f"{result.message} Повторная отправка будет доступна примерно через "
            f"{result.retry_after_seconds} сек.",
        )
    else:
        messages.info(request, result.message)
    return redirect(_verification_redirect_url(email, next_url))


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect("frontend:auth")


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)
