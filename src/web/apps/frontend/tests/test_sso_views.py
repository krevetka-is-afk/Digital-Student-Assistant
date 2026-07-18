from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch
from urllib.parse import unquote
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

User = get_user_model()

pytestmark = pytest.mark.django_db


def _uid():
    return uuid4().hex[:8]


def _make_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{body}.fakesig"


# ---------------------------------------------------------------------------
# sso_hse_redirect
# ---------------------------------------------------------------------------

def test_redirect_without_client_id_shows_error():
    with override_settings(HSE_OAUTH2_CLIENT_ID=""):
        response = Client().get(reverse("frontend:sso_hse_redirect"))
    assert response.status_code == 302
    assert reverse("frontend:auth") in response["Location"]


@override_settings(
    HSE_OAUTH2_CLIENT_ID="test-client-id",
    HSE_OAUTH2_AUTHORIZE_URL="https://auth.hse.ru/adfs/oauth2/authorize",
)
def test_redirect_with_client_id_goes_to_hse():
    response = Client().get(reverse("frontend:sso_hse_redirect"))
    assert response.status_code == 302
    location = response["Location"]
    assert "auth.hse.ru" in location
    assert "test-client-id" in location
    assert "response_type=code" in location


@override_settings(
    HSE_OAUTH2_CLIENT_ID="test-client-id",
    HSE_OAUTH2_AUTHORIZE_URL="https://auth.hse.ru/adfs/oauth2/authorize",
)
def test_redirect_includes_callback_url():
    response = Client().get(reverse("frontend:sso_hse_redirect"))
    assert response.status_code == 302
    assert "sso/hse/callback" in unquote(response["Location"])


# ---------------------------------------------------------------------------
# sso_hse_callback — error cases
# ---------------------------------------------------------------------------

def test_callback_with_error_param_redirects_to_auth():
    response = Client().get(
        reverse("frontend:sso_hse_callback") + "?error=access_denied"
    )
    assert response.status_code == 302
    assert reverse("frontend:auth") in response["Location"]


def test_callback_without_code_redirects_to_auth():
    response = Client().get(reverse("frontend:sso_hse_callback"))
    assert response.status_code == 302
    assert reverse("frontend:auth") in response["Location"]


@override_settings(HSE_OAUTH2_CLIENT_ID="id", HSE_OAUTH2_CLIENT_SECRET="")
def test_callback_without_client_secret_redirects_to_auth():
    response = Client().get(
        reverse("frontend:sso_hse_callback") + "?code=someauthcode"
    )
    assert response.status_code == 302
    assert reverse("frontend:auth") in response["Location"]


# ---------------------------------------------------------------------------
# sso_hse_callback — token exchange failure
# ---------------------------------------------------------------------------

@override_settings(
    HSE_OAUTH2_CLIENT_ID="id",
    HSE_OAUTH2_CLIENT_SECRET="secret",
    HSE_OAUTH2_TOKEN_URL="https://auth.hse.ru/adfs/oauth2/token",
)
def test_callback_token_exchange_failure_shows_error():
    with patch("apps.frontend.views.sso.urllib.request.urlopen", side_effect=Exception("timeout")):
        response = Client().get(
            reverse("frontend:sso_hse_callback") + "?code=someauthcode"
        )
    assert response.status_code == 302
    assert reverse("frontend:auth") in response["Location"]


# ---------------------------------------------------------------------------
# sso_hse_callback — happy path: new user created
# ---------------------------------------------------------------------------

@override_settings(
    HSE_OAUTH2_CLIENT_ID="id",
    HSE_OAUTH2_CLIENT_SECRET="secret",
    HSE_OAUTH2_TOKEN_URL="https://auth.hse.ru/adfs/oauth2/token",
)
def test_callback_creates_new_user_and_logs_in():
    email = f"newuser-{_uid()}@edu.hse.ru"
    jwt = _make_jwt({"email": email, "given_name": "Иван", "family_name": "Иванов"})
    token_response = json.dumps({"id_token": jwt}).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = token_response
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("apps.frontend.views.sso.urllib.request.urlopen", return_value=mock_resp):
        client = Client()
        # Seed the session with a valid OAuth2 state (normally done by sso_hse_redirect)
        state = "test-csrf-state-new-user"
        session = client.session
        session["oauth2_hse_state"] = state
        session.save()
        response = client.get(reverse("frontend:sso_hse_callback") + f"?code=abc&state={state}")

    assert response.status_code == 302
    assert User.objects.filter(email=email).exists()
    user = User.objects.get(email=email)
    assert user.first_name == "Иван"
    assert user.last_name == "Иванов"


@override_settings(
    HSE_OAUTH2_CLIENT_ID="id",
    HSE_OAUTH2_CLIENT_SECRET="secret",
    HSE_OAUTH2_TOKEN_URL="https://auth.hse.ru/adfs/oauth2/token",
)
def test_callback_logs_in_existing_user():
    email = f"existing-{_uid()}@edu.hse.ru"
    existing = User.objects.create_user(username=email, email=email, password="pass")

    jwt = _make_jwt({"email": email, "given_name": "Пётр", "family_name": "Петров"})
    token_response = json.dumps({"id_token": jwt}).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = token_response
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("apps.frontend.views.sso.urllib.request.urlopen", return_value=mock_resp):
        client = Client()
        # Seed the session with a valid OAuth2 state (normally done by sso_hse_redirect)
        state = "test-csrf-state-existing-user"
        session = client.session
        session["oauth2_hse_state"] = state
        session.save()
        response = client.get(reverse("frontend:sso_hse_callback") + f"?code=abc&state={state}")

    assert response.status_code == 302
    assert User.objects.filter(email=email).count() == 1
    existing.refresh_from_db()
    assert existing.first_name == "Пётр"


@override_settings(
    HSE_OAUTH2_CLIENT_ID="id",
    HSE_OAUTH2_CLIENT_SECRET="secret",
    HSE_OAUTH2_TOKEN_URL="https://auth.hse.ru/adfs/oauth2/token",
)
def test_callback_missing_email_in_token_redirects_to_auth():
    jwt = _make_jwt({"sub": "12345"})
    token_response = json.dumps({"id_token": jwt}).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = token_response
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("apps.frontend.views.sso.urllib.request.urlopen", return_value=mock_resp):
        response = Client().get(reverse("frontend:sso_hse_callback") + "?code=abc")

    assert response.status_code == 302
    assert reverse("frontend:auth") in response["Location"]
