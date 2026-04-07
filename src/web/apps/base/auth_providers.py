from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping

from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    provider: str
    subject: str
    username: str
    email: str
    first_name: str
    last_name: str
    roles: tuple[str, ...]


class AuthenticationProvider(ABC):
    name: str

    @abstractmethod
    def authenticate(self, request) -> ExternalIdentity | None:
        """Return external identity if provider can authenticate request."""


class HeaderSSOAuthenticationProvider(AuthenticationProvider):
    name = "sso-header-adapter"

    def authenticate(self, request) -> ExternalIdentity | None:
        meta = request.META
        subject = (meta.get(settings.AUTH_SSO_HEADER_SUBJECT) or "").strip()
        if not subject:
            return None

        username = (meta.get(settings.AUTH_SSO_HEADER_USERNAME) or "").strip()
        email = (meta.get(settings.AUTH_SSO_HEADER_EMAIL) or "").strip()
        first_name = (meta.get(settings.AUTH_SSO_HEADER_FIRST_NAME) or "").strip()
        last_name = (meta.get(settings.AUTH_SSO_HEADER_LAST_NAME) or "").strip()
        raw_roles = (meta.get(settings.AUTH_SSO_HEADER_ROLES) or "").strip()

        self._validate_signature(
            meta=meta,
            subject=subject,
            username=username,
            email=email,
            raw_roles=raw_roles,
        )

        roles = _parse_external_roles(raw_roles, separator=settings.AUTH_SSO_ROLE_SEPARATOR)
        return ExternalIdentity(
            provider=self.name,
            subject=subject,
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            roles=roles,
        )

    def _validate_signature(
        self,
        *,
        meta: Mapping[str, str],
        subject: str,
        username: str,
        email: str,
        raw_roles: str,
    ) -> None:
        secret = settings.AUTH_SSO_SHARED_SECRET
        if not secret:
            # Insecure mode is allowed only when explicitly enabled in settings.
            return

        signature_header = settings.AUTH_SSO_HEADER_SIGNATURE
        signature = (meta.get(signature_header) or "").strip()
        if not signature:
            raise AuthenticationFailed("Missing SSO signature header.")

        payload = "|".join([subject, username, email, raw_roles])
        expected = hmac.new(
            key=secret.encode("utf-8"),
            msg=payload.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise AuthenticationFailed("Invalid SSO signature.")


def get_authentication_provider() -> AuthenticationProvider | None:
    if not settings.AUTH_ENABLE_SSO:
        return None

    provider_name = settings.AUTH_SSO_PROVIDER
    if provider_name == "header":
        return HeaderSSOAuthenticationProvider()

    raise RuntimeError(f"Unsupported SSO provider: {provider_name!r}")


def resolve_local_role(
    external_roles: tuple[str, ...],
    *,
    role_map: Mapping[str, str],
    allowed_roles: set[str],
) -> str | None:
    for external_role in external_roles:
        local_role = role_map.get(external_role.lower())
        if local_role in allowed_roles:
            return local_role
    return None


def stable_username_from_subject(subject: str, *, max_length: int) -> str:
    raw = (subject or "").strip()
    if not raw:
        raise AuthenticationFailed("SSO subject is required.")
    candidate = f"sso:{raw}"
    if len(candidate) <= max_length:
        return candidate
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"sso:{digest}"


def _parse_external_roles(raw_roles: str, *, separator: str) -> tuple[str, ...]:
    if not raw_roles:
        return ()

    roles: list[str] = []
    seen: set[str] = set()
    for role in raw_roles.split(separator):
        normalized = role.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        roles.append(normalized)
    return tuple(roles)
