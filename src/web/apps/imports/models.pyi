from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from django.db import models

class ImportRun(models.Model):
    objects: ClassVar[models.Manager[ImportRun]]
    _meta: ClassVar[Any]

    id: int
    pk: int | None
    source: str
    source_name: str
    status: str
    imported_by_id: int | None
    stats: dict[str, object]
    error_message: str
    started_at: datetime
    finished_at: datetime | None

    def __str__(self) -> str: ...
