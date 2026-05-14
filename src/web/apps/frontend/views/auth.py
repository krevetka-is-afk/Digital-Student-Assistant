from urllib.parse import urlencode, urlsplit

from apps.users.email_verification import (
    VERIFICATION_GENERIC_RESEND_MESSAGE,
    is_user_pending_email_verification,
    resend_signup_code,
    verify_signup_code,
)
from apps.users.models import (
    UserRole,
)
from apps.users.registration import register_user
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
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

_CONSENT_ACCEPTED_VALUES = {"1", "true", "on", "yes"}


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
    reg_personal_data_consent = False
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
            reg_personal_data_consent = (
                    request.POST.get("personal_data_consent", "").strip().lower()
                    in _CONSENT_ACCEPTED_VALUES
            )

            result = register_user(
                email=reg_email,
                password=password,
                full_name=reg_name,
                role=reg_role,
                personal_data_consent=reg_personal_data_consent,
            )
            if result.success:
                if result.status == "access_request_created":
                    messages.info(request, result.message)
                    return redirect("frontend:auth")

                messages.success(request, result.message)
                return redirect(_verification_redirect_url(result.normalized_email, next_url))

            register_errors = {
                field: messages_list[0] for field, messages_list in result.field_errors.items()
            }

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
            "reg_personal_data_consent": reg_personal_data_consent,
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


def error_403(request, exception=None):
    return render(request, "403.html", status=403)


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)
