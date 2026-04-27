from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from django.db import models

class UserRole(models.TextChoices):
    STUDENT: ClassVar[str]
    CUSTOMER: ClassVar[str]
    CPPRP: ClassVar[str]
    values: ClassVar[list[str]]


class EmailVerificationPurpose(models.TextChoices):
    SIGNUP: ClassVar[str]
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
    email_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @property
    def is_email_verified(self) -> bool: ...
    def __str__(self) -> str: ...
    def mark_email_verified(self, verified_at: datetime | None = None) -> None: ...
    def set_favorite_project_ids(self, project_ids: list[int]) -> None: ...


class EmailVerificationCode(models.Model):
    objects: ClassVar[models.Manager[EmailVerificationCode]]
    _meta: ClassVar[Any]

    id: int
    pk: int | None
    user_id: int
    user: Any
    email: str
    purpose: str
    code_hash: str
    expires_at: datetime
    sent_at: datetime
    consumed_at: datetime | None
    attempt_count: int

    @property
    def is_consumed(self) -> bool: ...
    @property
    def is_expired(self) -> bool: ...
    def __str__(self) -> str: ...
