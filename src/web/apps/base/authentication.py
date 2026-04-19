import secrets
from dataclasses import dataclass

from django.conf import settings
from rest_framework.authentication import (
    BaseAuthentication,
    get_authorization_header,
)
from rest_framework.authentication import (
    TokenAuthentication as BaseTokenAuth,
)


@dataclass(frozen=True)
class ServicePrincipal:
    service_name: str

    is_service: bool = True
    is_staff: bool = False
    id: None = None

    @property
    def is_authenticated(self) -> bool:
        return True


class ServiceTokenAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth = get_authorization_header(request).split()
        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None
        if len(auth) != 2:
            return None

        presented_token = auth[1].decode(errors="ignore")
        service_tokens = getattr(settings, "OUTBOX_SERVICE_TOKENS", {}) or {}
        for service_name, service_token in service_tokens.items():
            if secrets.compare_digest(str(service_token), presented_token):
                principal = ServicePrincipal(service_name=str(service_name))
                return principal, {"service_name": principal.service_name, "auth_type": "service"}
        return None


class TokenAuthentication(BaseTokenAuth):
    keyword = "Bearer"
