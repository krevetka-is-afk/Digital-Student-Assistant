from urllib.parse import urlencode, urlsplit

from apps.frontend.forms import LoginForm, RegisterForm
from apps.users.email_verification import (
    VERIFICATION_GENERIC_RESEND_MESSAGE,
    create_signup_verification,
    is_user_pending_email_verification,
    resend_signup_code,
    verify_signup_code,
)
from apps.users.models import (
    ExternalAccessAllowlist,
    ExternalAccessRequest,
    ExternalAccessRequestStatus,
    UserProfile,
    UserRole,
    normalize_email,
)
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.decorators.http import require_POST

User = get_user_model()


def _safe_redirect_target(raw_next_url: str) -> str:
    candidate = (raw_next_url or "").strip()
    if not candidate:
        return reverse("frontend:project_list")
    path = urlsplit(candidate).path
    if path in {reverse("frontend:project_list"), reverse("frontend:auth")}:
        return path
    return reverse("frontend:project_list")


def _build_unique_username(email: str) -> str:
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


def _corporate_email_domains() -> set[str]:
    configured = getattr(settings, "ALLOWED_CORPORATE_EMAIL_DOMAINS", ["edu.hse.ru"])
    return {domain.strip().lower() for domain in configured if domain.strip()}


def _is_corporate_email(email: str) -> bool:
    normalized = normalize_email(email)
    _, _, domain = normalized.partition("@")
    return bool(domain) and domain in _corporate_email_domains()


def _external_email_is_allowlisted(email: str, role: str) -> bool:
    return ExternalAccessAllowlist.objects.filter(
        email=normalize_email(email),
        allowed_role=role,
        is_active=True,
    ).exists()


def _create_or_refresh_external_access_request(
    *,
    email: str,
    full_name: str,
    requested_role: str,
) -> None:
    ExternalAccessRequest.objects.update_or_create(
        email=normalize_email(email),
        defaults={
            "full_name": full_name,
            "requested_role": requested_role,
            "status": ExternalAccessRequestStatus.PENDING,
            "decision_note": "",
            "reviewed_by": None,
            "reviewed_at": None,
        },
    )


class AuthView(View):
    template_name = "frontend/auth.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("frontend:project_list")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        next_url = request.GET.get("next", "").strip()
        return render(
            request,
            self.template_name,
            self._build_context(
                active_tab="login",
                next_url=next_url,
                login_form=LoginForm(),
                register_form=RegisterForm(),
            ),
        )

    def post(self, request):
        active_tab = request.POST.get("tab", "login")
        next_url = request.POST.get("next", request.GET.get("next", "")).strip()

        is_login_post = active_tab == "login"
        is_register_post = active_tab == "register"

        login_form = LoginForm(request.POST if is_login_post else None)
        register_form = RegisterForm(request.POST if is_register_post else None)

        login_requires_email_verification = False

        if is_login_post and login_form.is_valid():
            response, login_requires_email_verification = self._handle_login(
                request, login_form, next_url
            )
            if response is not None:
                return response

        elif is_register_post and register_form.is_valid():
            response = self._handle_register(request, register_form, next_url)
            if response is not None:
                return response

        login_email = login_form["email"].value() or "" if login_form.is_bound else ""

        return render(
            request,
            self.template_name,
            self._build_context(
                active_tab=active_tab,
                next_url=next_url,
                login_form=login_form,
                register_form=register_form,
                login_requires_email_verification=login_requires_email_verification,
                login_email=login_email,
            ),
        )

    @staticmethod
    def _handle_login(
        request,
        form: LoginForm,
        next_url: str,
    ) -> tuple[HttpResponse | None, bool]:
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]

        user_obj = User.objects.filter(email__iexact=email).first()
        user = (
            authenticate(request, username=user_obj.username, password=password)
            if user_obj
            else None
        )

        if user is not None:
            auth_login(request, user)
            return redirect(_safe_redirect_target(next_url)), False

        if (
            user_obj is not None
            and is_user_pending_email_verification(user_obj)
            and user_obj.check_password(password)
        ):
            form.add_error(None, "Подтвердите email, чтобы войти.")
            return None, True

        form.add_error(None, "Неверный email или пароль.")
        return None, False

    @staticmethod
    def _handle_register(
        request,
        form: RegisterForm,
        next_url: str,
    ) -> HttpResponse | None:
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        name = form.cleaned_data["name"]
        role = form.cleaned_data["role"]

        if (
            role == UserRole.CUSTOMER
            and not _is_corporate_email(email)
            and not _external_email_is_allowlisted(email, role)
        ):
            _create_or_refresh_external_access_request(
                email=email,
                full_name=name,
                requested_role=role,
            )
            messages.info(
                request,
                "Заявка на внешний доступ отправлена. После одобрения ЦППРП "
                "вы сможете завершить регистрацию с этим email.",
            )
            return redirect("frontend:auth")

        with transaction.atomic():
            new_user = User.objects.create_user(
                username=_build_unique_username(email),
                email=email,
                password=password,
                is_active=False,
            )
            parts = name.split(None, 1)
            if parts:
                new_user.first_name = parts[0]
                new_user.last_name = parts[1] if len(parts) > 1 else ""
                new_user.save(update_fields=["first_name", "last_name"])

            UserProfile.objects.create(user=new_user, role=role)
            create_signup_verification(new_user)

        messages.success(request, "Мы отправили код подтверждения на указанный email.")
        return redirect(_verification_redirect_url(email, next_url))

    def _build_context(
        self,
        *,
        active_tab: str = "login",
        next_url: str = "",
        login_form: LoginForm | None = None,
        register_form: RegisterForm | None = None,
        login_requires_email_verification: bool = False,
        login_email: str = "",
    ) -> dict:
        return {
            "active_tab": active_tab,
            "next": next_url,
            "login_form": login_form or LoginForm(),
            "register_form": register_form or RegisterForm(),
            "login_requires_email_verification": login_requires_email_verification,
            "login_email": login_email,
            "UserRole": UserRole,
        }


class VerifyEmailView(View):
    template_name = "frontend/verify_email.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("frontend:project_list")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(
            request,
            self.template_name,
            self._build_context(
                email=request.GET.get("email", "").strip().lower(),
                next_url=request.GET.get("next", "").strip(),
            ),
        )

    def post(self, request):
        email = request.POST.get("email", "").strip().lower()
        code = request.POST.get("code", "").strip()
        next_url = request.POST.get("next", "").strip()
        errors: dict[str, str] = {}

        result = verify_signup_code(email=email, code=code)
        if result.success and result.user is not None:
            auth_login(request, result.user)
            messages.success(request, f"Добро пожаловать, {result.user.username}!")
            return redirect(_safe_redirect_target(next_url))

        if result.error_code == "missing_fields":
            if not email:
                errors["email"] = "Введите email."
            if not code:
                errors["code"] = "Введите код подтверждения."
        else:
            errors["general"] = result.message

        return render(
            request,
            self.template_name,
            self._build_context(
                email=email,
                code=code,
                next_url=next_url,
                errors=errors,
            ),
        )

    def _build_context(
        self,
        *,
        email: str = "",
        code: str = "",
        next_url: str = "",
        errors: dict[str, str] | None = None,
    ) -> dict:
        return {
            "email": email,
            "code": code,
            "next": next_url,
            "errors": errors or {},
            "generic_resend_message": VERIFICATION_GENERIC_RESEND_MESSAGE,
        }


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
