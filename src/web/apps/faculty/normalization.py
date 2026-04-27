from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^\w\s@.+-]+", re.UNICODE)


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = PUNCT_RE.sub(" ", text)
    return SPACE_RE.sub(" ", text).strip()


def stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def source_key_for_person(payload: dict[str, Any]) -> str:
    person_id = payload.get("person_id")
    if person_id not in (None, ""):
        return f"hse:{person_id}"
    profile_url = str(payload.get("profile_url") or "").strip()
    return f"url:{profile_url}"


def course_key(*, person_source_key: str, payload: dict[str, Any]) -> str:
    title = normalize_text(payload.get("title"))
    academic_year = normalize_text(payload.get("academic_year"))
    url = normalize_text(payload.get("url"))
    identity = "|".join([person_source_key, title, academic_year, url])
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def extract_emails(payload: dict[str, Any]) -> list[str]:
    contacts = payload.get("contacts") or {}
    values: list[Any] = []
    if isinstance(contacts, dict):
        for key in ("email", "emails", "mail", "mails"):
            value = contacts.get(key)
            if isinstance(value, list):
                values.extend(value)
            elif value:
                values.append(value)
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        email = str(raw).strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        normalized.append(email)
    return normalized
