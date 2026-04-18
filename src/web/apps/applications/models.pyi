from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from apps.projects.models import Project
from django.db import models

class ApplicationStatus(models.TextChoices):
    SUBMITTED: ClassVar[str]
    ACCEPTED: ClassVar[str]
    REJECTED: ClassVar[str]
    values: ClassVar[list[str]]


class Application(models.Model):
    objects: ClassVar[models.Manager[Application]]
    _meta: ClassVar[Any]

    id: int
    pk: int | None
    project_id: int
    project: Project
    applicant_id: int
    applicant: Any
    status: str
    motivation: str
    review_comment: str
    reviewed_by_id: int | None
    reviewed_by: Any | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str: ...
