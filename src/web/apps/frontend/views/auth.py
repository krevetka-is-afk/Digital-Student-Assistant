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
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST


def _safe_redirect_target(request, raw_next_url: str) -> str:
    candidate = raw_next_url.strip()
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse("frontend:project_list")


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

    if request.method == "POST":
        next_url = request.POST.get("next", next_url).strip()

        # ── LOGIN ──────────────────────────────────────────────────────────
        if active_tab == "login":
            login_email = request.POST.get("email", "").strip()
            password    = request.POST.get("password", "")

            if not login_email:
                login_errors["email"] = "Введите email."
            if not password:
                login_errors["password"] = "Введите пароль."

            if not login_errors:
                User = get_user_model()
                try:
                    user_obj = User.objects.get(email__iexact=login_email)
                    user = authenticate(request, username=user_obj.username, password=password)
                except User.DoesNotExist:
                    user = None

                if user is not None:
                    auth_login(request, user)
                    return redirect(_safe_redirect_target(request, next_url))
                else:
                    login_errors["general"] = "Неверный email или пароль."

        # ── REGISTER ───────────────────────────────────────────────────────
        elif active_tab == "register":
            reg_email = request.POST.get("email", "").strip().lower()
            password  = request.POST.get("password", "")
            reg_name  = request.POST.get("name", "").strip()
            reg_role  = request.POST.get("role", UserRole.STUDENT)

            if not reg_email:
                register_errors["email"] = "Введите email."
            if not password:
                register_errors["password"] = "Введите пароль."
            elif len(password) < 8:
                register_errors["password"] = "Пароль должен содержать не менее 8 символов."
            if reg_role not in {UserRole.STUDENT, UserRole.CUSTOMER}:
                reg_role = UserRole.STUDENT

            if not register_errors:
                User = get_user_model()
                if User.objects.filter(email__iexact=reg_email).exists():
                    register_errors["email"] = "Пользователь с таким email уже существует."
                else:
                    # Build unique username from email prefix
                    base = reg_email.split("@")[0]
                    username, n = base, 1
                    while User.objects.filter(username=username).exists():
                        username = f"{base}{n}"
                        n += 1

                    new_user = User.objects.create_user(
                        username=username,
                        email=reg_email,
                        password=password,
                    )
                    if reg_name:
                        parts = reg_name.split(" ", 1)
                        new_user.first_name = parts[0]
                        new_user.last_name  = parts[1] if len(parts) > 1 else ""
                        new_user.save(update_fields=["first_name", "last_name"])

                    UserProfile.objects.create(user=new_user, role=reg_role)
                    auth_login(request, new_user)
                    messages.success(request, f"Добро пожаловать, {new_user.username}!")
                    return redirect("frontend:project_list")

    return render(request, "frontend/auth.html", {
        "active_tab":      active_tab,
        "next":            next_url,
        "login_errors":    login_errors,
        "register_errors": register_errors,
        "login_email":     login_email,
        "reg_email":       reg_email,
        "reg_name":        reg_name,
        "reg_role":        reg_role,
        "UserRole":        UserRole,
    })


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect("frontend:auth")


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)
