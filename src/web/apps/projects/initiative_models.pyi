from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from django.db import models

from .models import Project

class InitiativeProposalStatus(models.TextChoices):
    DRAFT: ClassVar[str]
    ON_MODERATION: ClassVar[str]
    REVISION_REQUESTED: ClassVar[str]
    PUBLISHED: ClassVar[str]
    values: ClassVar[list[str]]


class InitiativeProposal(models.Model):
    objects: ClassVar[models.Manager[InitiativeProposal]]
    _meta: ClassVar[Any]

    id: int
    pk: int | None
    owner_id: int
    owner: Any
    title: str
    description: str
    tech_tags: list[str]
    team_size: int
    study_course: int | None
    education_program: str
    supervisor_name: str
    supervisor_email: str
    supervisor_department: str
    participants: list[dict[str, object]]
    status: str
    latest_submission_number: int
    moderated_by_id: int | None
    moderated_by: Any | None
    moderated_at: datetime | None
    moderation_comment: str
    published_project_id: int | None
    published_project: Project | None
    created_at: datetime
    updated_at: datetime
    submissions: Any

    def __str__(self) -> str: ...
    def build_submission_snapshot(self) -> dict[str, object]: ...


class InitiativeProposalSubmission(models.Model):
    objects: ClassVar[models.Manager[InitiativeProposalSubmission]]
    _meta: ClassVar[Any]

    class Decision(models.TextChoices):
        PENDING: ClassVar[str]
        APPROVED: ClassVar[str]
        REJECTED: ClassVar[str]
        values: ClassVar[list[str]]

    id: int
    pk: int | None
    proposal_id: int
    proposal: InitiativeProposal
    submission_number: int
    snapshot: dict[str, object]
    submitted_by_id: int | None
    submitted_by: Any | None
    submitted_at: datetime
    decision: str
    comment: str
    reviewed_by_id: int | None
    reviewed_by: Any | None
    reviewed_at: datetime | None
    published_project_id: int | None
    published_project: Project | None

    def __str__(self) -> str: ...
