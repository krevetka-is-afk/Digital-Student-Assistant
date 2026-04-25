from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from django.db import models

class DeadlineAudience(models.TextChoices):
    STUDENT: ClassVar[str]
    CUSTOMER: ClassVar[str]
    CPPRP: ClassVar[str]
    GLOBAL: ClassVar[str]
    values: ClassVar[list[str]]


class PlatformDeadline(models.Model):
    objects: ClassVar[models.Manager[PlatformDeadline]]
    _meta: ClassVar[Any]

    id: int
    pk: int | None
    slug: str
    title: str
    audience: str
    description: str
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str: ...


class DocumentTemplate(models.Model):
    objects: ClassVar[models.Manager[DocumentTemplate]]
    _meta: ClassVar[Any]

    id: int
    pk: int | None
    slug: str
    title: str
    audience: str
    url: str
    description: str
    is_active: bool
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str: ...
