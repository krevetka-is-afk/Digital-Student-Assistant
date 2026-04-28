import re
from collections.abc import Iterable

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_technology_tag(value: object) -> str:
    return _WHITESPACE_RE.sub(" ", str(value).strip().lower())


def normalize_technology_tags(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, Iterable):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        tag = normalize_technology_tag(raw_value)
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized
