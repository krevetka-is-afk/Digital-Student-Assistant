from __future__ import annotations

import json
import urllib.request
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect
from django.urls import reverse


def sso_hse_redirect(request):
    client_id = getattr(settings, "HSE_OAUTH2_CLIENT_ID", "").strip()
    if not client_id:
        messages.error(
            request,
            "SSO через edu.hse.ru временно недоступен — обратитесь к администратору.",
        )
        return redirect(reverse("frontend:auth"))

    callback_url = request.build_absolute_uri(reverse("frontend:sso_hse_callback"))
    authorize_url = getattr(
        settings,
        "HSE_OAUTH2_AUTHORIZE_URL",
        "https://auth.hse.ru/adfs/oauth2/authorize",
    )
    params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": "openid email profile",
        }
    )
    return redirect(f"{authorize_url}?{params}")


def sso_hse_callback(request):
    error = request.GET.get("error", "").strip()
    code = request.GET.get("code", "").strip()

    if error or not code:
        messages.error(request, f"SSO: {error or 'авторизация отменена'}")
        return redirect(reverse("frontend:auth"))

    client_id = getattr(settings, "HSE_OAUTH2_CLIENT_ID", "").strip()
    client_secret = getattr(settings, "HSE_OAUTH2_CLIENT_SECRET", "").strip()
    token_url = getattr(
        settings,
        "HSE_OAUTH2_TOKEN_URL",
        "https://auth.hse.ru/adfs/oauth2/token",
    )

    if not client_id or not client_secret:
        messages.info(
            request,
            "SSO через edu.hse.ru: для активации необходимо настроить "
            "HSE_OAUTH2_CLIENT_ID и HSE_OAUTH2_CLIENT_SECRET в конфигурации.",
        )
        return redirect(reverse("frontend:auth"))

    callback_url = request.build_absolute_uri(reverse("frontend:sso_hse_callback"))
    token_payload = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": callback_url,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        token_url,
        data=token_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_response = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        messages.error(request, f"SSO: не удалось получить токен — {exc}")
        return redirect(reverse("frontend:auth"))

    id_token = token_response.get("id_token", "")
    if not id_token:
        messages.error(request, "SSO: id_token не получен от сервера HSE")
        return redirect(reverse("frontend:auth"))

    # Decode JWT payload (base64, no signature verification needed for user info)
    try:
        import base64

        payload_b64 = id_token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception:
        messages.error(request, "SSO: не удалось прочитать токен пользователя")
        return redirect(reverse("frontend:auth"))

    user_email = (payload.get("email") or payload.get("upn") or "").strip().lower()
    user_first = payload.get("given_name", "")
    user_last = payload.get("family_name", "")

    if not user_email:
        messages.error(request, "SSO: сервер HSE не вернул email пользователя")
        return redirect(reverse("frontend:auth"))

    User = get_user_model()
    user, created = User.objects.get_or_create(
        email=user_email,
        defaults={
            "username": user_email,
            "first_name": user_first,
            "last_name": user_last,
        },
    )
    if not created and (user_first or user_last):
        update_fields = []
        if user_first and user.first_name != user_first:
            user.first_name = user_first
            update_fields.append("first_name")
        if user_last and user.last_name != user_last:
            user.last_name = user_last
            update_fields.append("last_name")
        if update_fields:
            user.save(update_fields=update_fields)

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, f"Вы вошли через edu.hse.ru как {user_email}")
    return redirect(reverse("frontend:project_list"))
