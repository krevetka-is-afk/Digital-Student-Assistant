from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from apps.outbox.services import emit_event
from apps.projects.models import Project
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .client import FacultyClient
from .models import (
    FacultyAuthorship,
    FacultyCourse,
    FacultyMatchStatus,
    FacultyPerson,
    FacultyPublication,
    FacultySyncState,
    ProjectFacultyMatch,
)
from .normalization import (
    course_key,
    extract_emails,
    normalize_text,
    source_key_for_person,
    stable_hash,
)


@dataclass
class FacultySyncStats:
    persons_seen: int = 0
    persons_changed: int = 0
    publications_seen: int = 0
    publications_changed: int = 0
    courses_seen: int = 0
    courses_changed: int = 0
    matches_changed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "persons_seen": self.persons_seen,
            "persons_changed": self.persons_changed,
            "publications_seen": self.publications_seen,
            "publications_changed": self.publications_changed,
            "courses_seen": self.courses_seen,
            "courses_changed": self.courses_changed,
            "matches_changed": self.matches_changed,
            "errors": self.errors,
        }


def _parse_datetime(value: Any):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value
    return parse_datetime(str(value))


def _schedule_event(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    source_hash: str,
) -> None:
    idempotency_key = f"{event_type}:{aggregate_id}:{source_hash}"

    def _emit() -> None:
        emit_event(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            idempotency_key=idempotency_key,
            source="faculty-sync",
        )

    transaction.on_commit(_emit)


def faculty_person_payload(person: FacultyPerson) -> dict[str, Any]:
    return {
        "source_key": person.source_key,
        "source_person_id": person.source_person_id,
        "profile_url": person.source_profile_url,
        "full_name": person.full_name,
        "full_name_normalized": person.full_name_normalized,
        "primary_unit": person.primary_unit,
        "primary_unit_normalized": person.primary_unit_normalized,
        "campus_id": person.campus_id,
        "campus_name": person.campus_name,
        "publications_total": person.publications_total,
        "interests": person.interests,
        "languages": person.languages,
        "emails": person.emails,
        "is_stale": person.is_stale,
        "source_hash": person.source_hash,
        "updated_at": person.updated_at.isoformat() if person.updated_at else None,
    }


def faculty_publication_payload(publication: FacultyPublication) -> dict[str, Any]:
    authors = [
        {
            "person_source_key": authorship.person.source_key if authorship.person else None,
            "position": authorship.position,
            "display_name": authorship.display_name,
            "href": authorship.href,
        }
        for authorship in publication.authorships.select_related("person").order_by("position")
    ]
    return {
        "source_publication_id": publication.source_publication_id,
        "title": publication.title,
        "type": publication.publication_type,
        "year": publication.year,
        "language": publication.language,
        "url": publication.url,
        "created_at_source": (
            publication.created_at_source.isoformat() if publication.created_at_source else None
        ),
        "authors": authors,
        "source_hash": publication.source_hash,
    }


def faculty_course_payload(course: FacultyCourse) -> dict[str, Any]:
    return {
        "course_key": course.course_key,
        "person_source_key": course.person.source_key,
        "title": course.title,
        "url": course.url,
        "academic_year": course.academic_year,
        "language": course.language,
        "level": course.level,
        "source_hash": course.source_hash,
    }


def project_faculty_match_payload(match: ProjectFacultyMatch) -> dict[str, Any]:
    return {
        "project_id": str(match.project_id),
        "faculty_source_key": match.faculty_person.source_key if match.faculty_person else None,
        "status": match.status,
        "match_strategy": match.match_strategy,
        "confidence": float(match.confidence),
        "supervisor_name": match.supervisor_name,
        "supervisor_email": match.supervisor_email,
        "supervisor_department": match.supervisor_department,
        "candidate_person_ids": match.candidate_person_ids,
        "matched_at": match.matched_at.isoformat() if match.matched_at else None,
    }


def upsert_person(payload: dict[str, Any], *, seen_at) -> tuple[FacultyPerson, bool]:
    source_key = source_key_for_person(payload)
    source_person_id = str(payload.get("person_id") or "")
    profile_url = str(
        payload.get("profile_url") or f"https://www.hse.ru/org/persons/{source_person_id}"
    )
    public_payload = {
        "person_id": payload.get("person_id"),
        "full_name": payload.get("full_name"),
        "profile_url": profile_url,
        "primary_unit": payload.get("primary_unit"),
        "campus_name": payload.get("campus_name"),
        "publications_total": payload.get("publications_total") or 0,
        "languages": payload.get("languages") or [],
        "interests": payload.get("interests") or [],
    }
    source_hash = stable_hash(payload)
    defaults = {
        "source_person_id": source_person_id,
        "source_profile_url": profile_url,
        "full_name": str(payload.get("full_name") or ""),
        "full_name_normalized": normalize_text(payload.get("full_name")),
        "primary_unit": str(payload.get("primary_unit") or ""),
        "primary_unit_normalized": normalize_text(payload.get("primary_unit")),
        "campus_id": str(payload.get("campus_id") or ""),
        "campus_name": str(payload.get("campus_name") or ""),
        "publications_total": int(payload.get("publications_total") or 0),
        "emails": extract_emails(payload),
        "interests": payload.get("interests") or [],
        "languages": payload.get("languages") or [],
        "positions": payload.get("positions") or [],
        "relations": payload.get("relations") or {},
        "research_ids": payload.get("research_ids") or {},
        "public_payload": public_payload,
        "raw_payload": payload,
        "source_hash": source_hash,
        "source_seen_at": seen_at,
        "is_stale": False,
    }
    person, created = FacultyPerson.objects.get_or_create(source_key=source_key, defaults=defaults)
    changed = created or person.source_hash != source_hash or person.is_stale
    if changed:
        for field_name, value in defaults.items():
            setattr(person, field_name, value)
        person.save()
        _schedule_event(
            event_type="faculty.person.changed",
            aggregate_type="faculty_person",
            aggregate_id=person.source_key,
            payload=faculty_person_payload(person),
            source_hash=source_hash,
        )
    else:
        FacultyPerson.objects.filter(pk=person.pk).update(source_seen_at=seen_at)
    return person, changed


def upsert_publication(payload: dict[str, Any]) -> tuple[FacultyPublication, bool]:
    source_publication_id = str(payload.get("id") or "")
    source_hash = stable_hash(payload)
    defaults = {
        "title": str(payload.get("title") or ""),
        "publication_type": str(payload.get("type") or ""),
        "year": payload.get("year") if isinstance(payload.get("year"), int) else None,
        "language": str(payload.get("language") or ""),
        "url": str(payload.get("url") or ""),
        "created_at_source": _parse_datetime(payload.get("created_at")),
        "raw_payload": payload,
        "source_hash": source_hash,
    }
    publication, created = FacultyPublication.objects.get_or_create(
        source_publication_id=source_publication_id,
        defaults=defaults,
    )
    changed = created or publication.source_hash != source_hash
    if changed:
        for field_name, value in defaults.items():
            setattr(publication, field_name, value)
        publication.save()
    return publication, changed


def replace_authorships(publication: FacultyPublication, authors: list[dict[str, Any]]) -> None:
    FacultyAuthorship.objects.filter(publication=publication).delete()
    authorships: list[FacultyAuthorship] = []
    for index, author in enumerate(authors):
        if not isinstance(author, dict):
            continue
        person = None
        person_id = author.get("person_id")
        if person_id not in (None, ""):
            person = FacultyPerson.objects.filter(source_key=f"hse:{person_id}").first()
        authorships.append(
            FacultyAuthorship(
                publication=publication,
                person=person,
                position=int(author.get("position") or index),
                display_name=str(author.get("display_name") or ""),
                href=str(author.get("href") or ""),
            )
        )
    FacultyAuthorship.objects.bulk_create(authorships)


def upsert_course(person: FacultyPerson, payload: dict[str, Any]) -> tuple[FacultyCourse, bool]:
    key = course_key(person_source_key=person.source_key, payload=payload)
    source_hash = stable_hash(payload)
    defaults = {
        "person": person,
        "title": str(payload.get("title") or ""),
        "url": str(payload.get("url") or ""),
        "academic_year": str(payload.get("academic_year") or ""),
        "language": str(payload.get("language") or ""),
        "level": str(payload.get("level") or ""),
        "raw_meta": str(payload.get("raw_meta") or ""),
        "source_hash": source_hash,
    }
    course, created = FacultyCourse.objects.get_or_create(course_key=key, defaults=defaults)
    changed = created or course.source_hash != source_hash
    if changed:
        for field_name, value in defaults.items():
            setattr(course, field_name, value)
        course.save()
        _schedule_event(
            event_type="faculty.course.changed",
            aggregate_type="faculty_course",
            aggregate_id=course.course_key,
            payload=faculty_course_payload(course),
            source_hash=source_hash,
        )
    return course, changed


def sync_faculty(
    *,
    client: FacultyClient | None = None,
    limit: int | None = None,
    person_id: int | None = None,
) -> FacultySyncStats:
    stats = FacultySyncStats()
    client = client or FacultyClient.from_settings()
    started_at = timezone.now()
    state, _ = FacultySyncState.objects.get_or_create(resource="faculty")

    try:
        summaries = (
            [{"person_id": person_id}]
            if person_id is not None
            else client.iter_person_summaries(limit=limit)
        )
        for summary in summaries:
            person_id_value = summary.get("person_id")
            if person_id_value in (None, ""):
                continue
            with transaction.atomic():
                person_payload = client.get_person(person_id_value)
                person, person_changed = upsert_person(person_payload, seen_at=started_at)
                stats.persons_seen += 1
                stats.persons_changed += int(person_changed)

                publications = client.list_person_publications(person_id_value)
                for publication_payload in publications:
                    publication, publication_changed = upsert_publication(publication_payload)
                    replace_authorships(publication, publication_payload.get("authors") or [])
                    stats.publications_seen += 1
                    stats.publications_changed += int(publication_changed)
                    if publication_changed:
                        _schedule_event(
                            event_type="faculty.publication.changed",
                            aggregate_type="faculty_publication",
                            aggregate_id=publication.source_publication_id,
                            payload=faculty_publication_payload(publication),
                            source_hash=publication.source_hash,
                        )

                courses = client.list_person_courses(person_id_value)
                for course_payload in courses:
                    _, course_changed = upsert_course(person, course_payload)
                    stats.courses_seen += 1
                    stats.courses_changed += int(course_changed)

        stats.matches_changed = reconcile_project_faculty_matches()
        state.last_success_at = timezone.now()
        state.last_error = ""
        state.last_seen_at = started_at
        state.stats = stats.as_dict()
        state.save()
    except Exception as exc:
        state.last_error = str(exc)
        state.stats = stats.as_dict()
        state.save(update_fields=["last_error", "stats", "updated_at"])
        raise
    return stats


def reconcile_project_faculty_matches() -> int:
    changed_count = 0
    projects = Project.objects.exclude(supervisor_name="").only(
        "id",
        "supervisor_name",
        "supervisor_email",
        "supervisor_department",
    )
    for project in projects:
        match, changed = resolve_project_faculty_match(project)
        if changed:
            changed_count += 1
            _schedule_event(
                event_type="project_faculty_match.changed",
                aggregate_type="project_faculty_match",
                aggregate_id=str(project.pk),
                payload=project_faculty_match_payload(match),
                source_hash=stable_hash(project_faculty_match_payload(match)),
            )
    return changed_count


def resolve_project_faculty_match(project: Project) -> tuple[ProjectFacultyMatch, bool]:
    supervisor_name = str(project.supervisor_name or "").strip()
    supervisor_email = str(project.supervisor_email or "").strip().lower()
    supervisor_department = str(project.supervisor_department or "").strip()
    normalized_name = normalize_text(supervisor_name)
    normalized_department = normalize_text(supervisor_department)

    candidates = FacultyPerson.objects.none()
    if normalized_name:
        candidates = FacultyPerson.objects.filter(full_name_normalized=normalized_name)

    faculty_person = None
    status = FacultyMatchStatus.UNMATCHED
    strategy = ""
    confidence = Decimal("0")

    if supervisor_email:
        email_candidates = [
            candidate for candidate in candidates if supervisor_email in (candidate.emails or [])
        ]
        if len(email_candidates) == 1:
            faculty_person = email_candidates[0]
            status = FacultyMatchStatus.CONFIRMED
            strategy = "email_exact"
            confidence = Decimal("0.95")

    if faculty_person is None and normalized_department and candidates.exists():
        department_candidates = [
            candidate
            for candidate in candidates
            if _department_matches(normalized_department, candidate.primary_unit_normalized)
        ]
        if len(department_candidates) == 1:
            faculty_person = department_candidates[0]
            status = FacultyMatchStatus.CONFIRMED
            strategy = "name_department"
            confidence = Decimal("0.85")

    if faculty_person is None and normalized_name:
        candidate_count = candidates.count()
        if candidate_count == 1:
            faculty_person = candidates.first()
            status = FacultyMatchStatus.CANDIDATE
            strategy = "name_unique"
            confidence = Decimal("0.65")
        elif candidate_count > 1:
            status = FacultyMatchStatus.AMBIGUOUS
            strategy = "name_ambiguous"
            confidence = Decimal("0.20")

    candidate_person_ids = list(candidates.values_list("source_key", flat=True))
    existing_match = ProjectFacultyMatch.objects.filter(project=project).first()
    matched_at = existing_match.matched_at if existing_match else None
    if status == FacultyMatchStatus.CONFIRMED and matched_at is None:
        matched_at = timezone.now()

    defaults = {
        "faculty_person": faculty_person,
        "supervisor_name": supervisor_name,
        "supervisor_email": supervisor_email,
        "supervisor_department": supervisor_department,
        "match_strategy": strategy,
        "confidence": confidence,
        "status": status,
        "candidate_person_ids": candidate_person_ids,
        "matched_by": "system",
        "matched_at": matched_at if status == FacultyMatchStatus.CONFIRMED else None,
    }
    match, created = ProjectFacultyMatch.objects.get_or_create(project=project, defaults=defaults)
    changed = created or any(
        getattr(match, field_name) != value for field_name, value in defaults.items()
    )
    if changed:
        for field_name, value in defaults.items():
            setattr(match, field_name, value)
        match.save()
    return match, changed


def _department_matches(project_department: str, faculty_unit: str) -> bool:
    if not project_department or not faculty_unit:
        return False
    return project_department in faculty_unit or faculty_unit in project_department
