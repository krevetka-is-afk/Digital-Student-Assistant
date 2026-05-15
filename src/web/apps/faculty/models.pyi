from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from apps.projects.models import Project
from django.db import models

class FacultyMatchStatus(models.TextChoices):
    CANDIDATE: str
    CONFIRMED: str
    REJECTED: str
    AMBIGUOUS: str
    UNMATCHED: str

class FacultyPerson(models.Model):
    objects: models.Manager[FacultyPerson]
    source_person_id: str
    source_profile_url: str
    source_key: str
    full_name: str
    full_name_normalized: str
    primary_unit: str
    primary_unit_normalized: str
    campus_id: str
    campus_name: str
    publications_total: int
    emails: list[str]
    interests: list[str]
    languages: list[str]
    positions: list[Any]
    relations: dict[str, Any]
    research_ids: dict[str, Any]
    public_payload: dict[str, Any]
    raw_payload: dict[str, Any]
    source_hash: str
    source_seen_at: datetime | None
    synced_at: datetime
    is_stale: bool
    created_at: datetime
    updated_at: datetime
    authorships: models.Manager[FacultyAuthorship]
    courses: models.Manager[FacultyCourse]
    project_matches: models.Manager[ProjectFacultyMatch]

    def __str__(self) -> str: ...

class FacultyPublication(models.Model):
    objects: models.Manager[FacultyPublication]
    source_publication_id: str
    title: str
    publication_type: str
    year: int | None
    language: str
    url: str
    created_at_source: datetime | None
    raw_payload: dict[str, Any]
    source_hash: str
    synced_at: datetime
    created_at: datetime
    updated_at: datetime
    authorships: models.Manager[FacultyAuthorship]

    def __str__(self) -> str: ...

class FacultyAuthorship(models.Model):
    objects: models.Manager[FacultyAuthorship]
    publication: FacultyPublication
    publication_id: int
    person: FacultyPerson | None
    person_id: int | None
    position: int
    display_name: str
    href: str

class FacultyCourse(models.Model):
    objects: models.Manager[FacultyCourse]
    person: FacultyPerson
    person_id: int
    course_key: str
    title: str
    url: str
    academic_year: str
    language: str
    level: str
    raw_meta: str
    source_hash: str
    synced_at: datetime
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str: ...

class FacultySyncState(models.Model):
    objects: models.Manager[FacultySyncState]
    resource: str
    cursor: str
    last_success_at: datetime | None
    last_error: str
    last_seen_at: datetime | None
    stats: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str: ...

class ProjectFacultyMatch(models.Model):
    objects: models.Manager[ProjectFacultyMatch]
    project: Project
    project_id: int
    faculty_person: FacultyPerson | None
    faculty_person_id: int | None
    supervisor_name: str
    supervisor_email: str
    supervisor_department: str
    match_strategy: str
    confidence: Decimal
    status: str
    candidate_person_ids: list[str]
    matched_by: str
    matched_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str: ...
