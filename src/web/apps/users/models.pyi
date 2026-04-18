from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from django.db import models

class UserRole(models.TextChoices):
    STUDENT: ClassVar[str]
    CUSTOMER: ClassVar[str]
    CPPRP: ClassVar[str]
    values: ClassVar[list[str]]


class UserProfile(models.Model):
    objects: ClassVar[models.Manager[UserProfile]]
    _meta: ClassVar[Any]

    id: int
    pk: int | None
    user_id: int
    user: Any
    role: str
    bio: str
    interests: list[str]
    favorite_project_ids: list[int]
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str: ...
    def set_favorite_project_ids(self, project_ids: list[int]) -> None: ...
