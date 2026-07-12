from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
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
    messages.info(
        request,
        "SSO через edu.hse.ru: для активации необходимо настроить "
        "HSE_OAUTH2_CLIENT_ID и HSE_OAUTH2_CLIENT_SECRET в конфигурации.",
    )
    return redirect(reverse("frontend:auth"))
