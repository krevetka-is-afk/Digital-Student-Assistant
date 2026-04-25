from __future__ import annotations

from datetime import date, datetime
from typing import Any, ClassVar

from django.db import models

class ProjectStatus(models.TextChoices):
    CREATED: ClassVar[str]
    DRAFT: ClassVar[str]
    REVISION_REQUESTED: ClassVar[str]
    SUPERVISOR_REVIEW: ClassVar[str]
    ON_MODERATION: ClassVar[str]
    PUBLISHED: ClassVar[str]
    STAFFED: ClassVar[str]
    COMPLETED: ClassVar[str]
    CANCELLED: ClassVar[str]
    REJECTED: ClassVar[str]
    ARCHIVED: ClassVar[str]
    values: ClassVar[list[str]]

    @classmethod
    def catalog_values(cls) -> tuple[str, ...]: ...


class ProjectSourceType(models.TextChoices):
    SUPERVISOR: ClassVar[str]
    INITIATIVE: ClassVar[str]
    EPP: ClassVar[str]
    MANUAL: ClassVar[str]
    values: ClassVar[list[str]]


class EPP(models.Model):
    objects: ClassVar[models.Manager[EPP]]
    _meta: ClassVar[Any]

    id: int
    pk: int | None
    source_ref: str
    title: str
    campaign_ref: str
    campaign_title: str
    supervisor_name: str
    supervisor_email: str
    supervisor_department: str
    initiator_name: str
    initiator_type: str
    status_raw: str
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str: ...


class ProjectQuerySet(models.QuerySet[Project]):
    def published(self) -> ProjectQuerySet: ...
    def search(self, query: str, user: Any | None = None) -> ProjectQuerySet: ...


class ProjectManager(models.Manager[Project]):
    def get_queryset(self) -> ProjectQuerySet: ...
    def published(self) -> ProjectQuerySet: ...
    def search(self, query: str, user: Any | None = None) -> ProjectQuerySet: ...


class Project(models.Model):
    objects: ClassVar[ProjectManager]
    _meta: ClassVar[Any]

    id: int
    pk: int | None
    title: str
    description: str
    tech_tags: list[str]
    epp_id: int | None
    epp: EPP | None
    owner_id: int | None
    owner: Any | None
    status: str
    team_size: int
    accepted_participants_count: int
    source_type: str
    source_ref: str
    vacancy_title: str
    thesis_title: str
    implementation_features: str
    selection_criteria: str
    work_format: str
    student_participation_format: str
    supervisor_name: str
    status_raw: str
    python_libraries: str
    methods: str
    programming_languages: str
    data_tools: str
    vacancy_tags: str
    application_opened_at: date | None
    application_deadline: date | None
    moderation_comment: str
    moderated_by_id: int | None
    moderated_by: Any | None
    moderated_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    applications: Any

    def __str__(self) -> str: ...
    def save(self, *args: Any, **kwargs: Any) -> None: ...
    def build_source_description(self) -> str: ...
    def build_tech_tags(self) -> list[str]: ...
    def is_public(self) -> bool: ...
    def get_tags_list(self) -> list[str]: ...

    @property
    def is_team_project(self) -> bool: ...

    @property
    def staffing_state(self) -> str: ...

    @property
    def application_window_state(self) -> str: ...
