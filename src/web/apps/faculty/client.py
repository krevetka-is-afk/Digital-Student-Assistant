from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

import requests
from django.conf import settings


class FacultyClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class FacultyClient:
    base_url: str
    timeout: float

    @classmethod
    def from_settings(cls) -> "FacultyClient":
        base_url = str(getattr(settings, "FACULTY_SERVICE_URL", "") or "").rstrip("/")
        if not base_url:
            raise FacultyClientError("FACULTY_SERVICE_URL is not configured.")
        timeout = float(getattr(settings, "FACULTY_SERVICE_TIMEOUT", 10))
        return cls(base_url=base_url, timeout=timeout)

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1{path}"
        try:
            response = requests.get(url, params=params or {}, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise FacultyClientError(f"Faculty request failed: {url}") from exc
        except ValueError as exc:
            raise FacultyClientError(f"Faculty response is not JSON: {url}") from exc
        if not isinstance(payload, dict):
            raise FacultyClientError(f"Faculty response must be an object: {url}")
        return payload

    def iter_person_summaries(
        self,
        *,
        page_size: int = 100,
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        page = 1
        emitted = 0
        while True:
            payload = self._get("/persons", params={"page": page, "page_size": page_size})
            results = payload.get("results") or []
            if not isinstance(results, list):
                raise FacultyClientError("Faculty persons response has invalid results.")
            for item in results:
                if not isinstance(item, dict):
                    continue
                yield item
                emitted += 1
                if limit is not None and emitted >= limit:
                    return
            if not payload.get("next") or not results:
                return
            page += 1

    def get_person(self, person_id: int | str) -> dict[str, Any]:
        return self._get(f"/persons/{person_id}")

    def list_person_publications(
        self,
        person_id: int | str,
        *,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        return self._collect_paginated(f"/persons/{person_id}/publications", page_size=page_size)

    def list_person_courses(
        self,
        person_id: int | str,
        *,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        return self._collect_paginated(f"/persons/{person_id}/courses", page_size=page_size)

    def _collect_paginated(self, path: str, *, page_size: int) -> list[dict[str, Any]]:
        page = 1
        items: list[dict[str, Any]] = []
        while True:
            payload = self._get(path, params={"page": page, "page_size": page_size})
            results = payload.get("results") or []
            if not isinstance(results, list):
                raise FacultyClientError(f"Faculty response has invalid results: {path}")
            items.extend(item for item in results if isinstance(item, dict))
            if not payload.get("next") or not results:
                return items
            page += 1
