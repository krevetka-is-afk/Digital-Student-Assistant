from __future__ import annotations

from typing import Any, Protocol

import httpx

from .models import GraphEvent


class OutboxClient(Protocol):
    async def get_checkpoint(self) -> dict[str, Any]: ...

    async def fetch_events(
        self,
        *,
        mode: str,
        batch_size: int,
        replay_from_id: int | None = None,
    ) -> list[GraphEvent]: ...

    async def ack_event(self, *, event_id: int) -> dict[str, Any]: ...


class HttpOutboxClient:
    def __init__(
        self,
        *,
        base_url: str,
        consumer: str,
        timeout_sec: float,
        auth_header: str = "",
    ):
        self._base_url = base_url.rstrip("/")
        self._consumer = consumer
        self._timeout_sec = timeout_sec
        self._auth_header = auth_header.strip()

    def _headers(self) -> dict[str, str]:
        if not self._auth_header:
            return {}
        return {"Authorization": self._auth_header}

    async def get_checkpoint(self) -> dict[str, Any]:
        url = f"{self._base_url}/api/v1/outbox/consumers/{self._consumer}/checkpoint/"
        async with httpx.AsyncClient(timeout=self._timeout_sec, headers=self._headers()) as client:
            response = await client.get(url)
            response.raise_for_status()
        return dict(response.json())

    async def fetch_events(
        self,
        *,
        mode: str,
        batch_size: int,
        replay_from_id: int | None = None,
    ) -> list[GraphEvent]:
        params: dict[str, Any] = {
            "consumer": self._consumer,
            "mode": mode,
            "limit": batch_size,
        }
        if replay_from_id is not None:
            params["replay_from_id"] = replay_from_id

        url = f"{self._base_url}/api/v1/outbox/events/"
        async with httpx.AsyncClient(timeout=self._timeout_sec, headers=self._headers()) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict):
            items = payload.get("results") or []
        elif isinstance(payload, list):
            items = payload
        else:
            items = []

        events = [GraphEvent.model_validate(item) for item in items]
        return sorted(events, key=lambda item: item.id or 0)

    async def ack_event(self, *, event_id: int) -> dict[str, Any]:
        payload = {"consumer": self._consumer, "event_id": event_id}
        url = f"{self._base_url}/api/v1/outbox/events/ack/"
        async with httpx.AsyncClient(timeout=self._timeout_sec, headers=self._headers()) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        return dict(response.json())
