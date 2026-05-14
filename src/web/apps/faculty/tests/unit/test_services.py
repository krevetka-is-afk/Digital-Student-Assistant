from __future__ import annotations

from uuid import uuid4

from apps.faculty.models import FacultyCourse, FacultyMatchStatus, FacultyPerson
from apps.faculty.services import resolve_project_faculty_match, upsert_course, upsert_person
from apps.outbox.models import OutboxEvent
from apps.projects.models import Project, ProjectStatus
from django.utils import timezone


def _person_payload(**overrides):
    payload = {
        "person_id": 25477,
        "profile_url": f"https://www.hse.ru/org/persons/{uuid4().hex}",
        "full_name": "Иванов Иван Иванович",
        "primary_unit": "Факультет компьютерных наук",
        "campus_name": "Москва",
        "publications_total": 10,
        "languages": ["английский"],
        "interests": ["graph", "ml"],
        "contacts": {"emails": ["ivanov@example.com"]},
        "positions": [],
        "relations": {},
        "research_ids": {},
    }
    payload.update(overrides)
    return payload


def test_upsert_person_emits_event_only_when_hash_changes():
    token = uuid4().hex[:8]
    payload = _person_payload(person_id=token)

    person, changed = upsert_person(payload, seen_at=timezone.now())
    event_qs = OutboxEvent.objects.filter(
        event_type="faculty.person.changed",
        aggregate_id=f"hse:{token}",
    )

    assert changed is True
    assert person.source_key == f"hse:{token}"
    assert event_qs.count() == 1

    _, changed_again = upsert_person(payload, seen_at=timezone.now())

    assert changed_again is False
    assert event_qs.count() == 1


def test_upsert_course_preserves_long_external_course_fields():
    token = uuid4().hex[:8]
    person = FacultyPerson.objects.create(
        source_key=f"hse:course-{token}",
        source_person_id=f"course-{token}",
        source_profile_url=f"https://www.hse.ru/org/persons/course-{token}",
        full_name="Иванов Иван Иванович",
        full_name_normalized="иванов иван иванович",
        source_hash="hash",
    )
    payload = {
        "title": "Long metadata course",
        "url": "https://www.hse.ru/edu/courses/" + ("x" * 1200),
        "academic_year": "2025/2026 " + ("x" * 80),
        "language": "английский " + ("x" * 140),
        "level": "магистратура " + ("x" * 140),
        "raw_meta": "raw metadata is preserved",
    }

    course, changed = upsert_course(person, payload)

    assert changed is True
    assert len(course.url) == FacultyCourse._meta.get_field("url").max_length
    assert len(course.academic_year) == FacultyCourse._meta.get_field("academic_year").max_length
    assert course.language == payload["language"]
    assert course.level == payload["level"]
    assert course.raw_meta == "raw metadata is preserved"
    assert course.raw_payload == payload


def test_upsert_course_refreshes_existing_rows_when_schema_preserves_more_data():
    token = uuid4().hex[:8]
    person = FacultyPerson.objects.create(
        source_key=f"hse:refresh-{token}",
        source_person_id=f"refresh-{token}",
        source_profile_url=f"https://www.hse.ru/org/persons/refresh-{token}",
        full_name="Иванов Иван Иванович",
        full_name_normalized="иванов иван иванович",
        source_hash="hash",
    )
    payload = {
        "title": "Schema refresh course",
        "url": "https://www.hse.ru/edu/courses/schema-refresh",
        "academic_year": "2025/2026",
        "language": "русский",
        "level": "Аспирантура " + ("направление " * 30),
        "raw_meta": "fresh raw metadata",
    }
    course, _ = upsert_course(person, payload)
    course.level = course.level[:100]
    course.raw_payload = {}
    course.save(update_fields=["level", "raw_payload", "updated_at"])

    refreshed, changed = upsert_course(person, payload)

    assert changed is True
    assert refreshed.pk == course.pk
    assert refreshed.level == payload["level"]
    assert refreshed.raw_payload == payload


def test_resolve_project_faculty_match_confirms_email_exact():
    token = uuid4().hex[:8]
    full_name = f"Иванов Иван {token}"
    full_name_normalized = f"иванов иван {token}"
    email = f"ivanov-{token}@example.com"
    FacultyPerson.objects.create(
        source_key=f"hse:email-{token}",
        source_person_id=f"email-{token}",
        source_profile_url=f"https://www.hse.ru/org/persons/email-{token}",
        full_name=full_name,
        full_name_normalized=full_name_normalized,
        primary_unit="Факультет компьютерных наук",
        primary_unit_normalized="факультет компьютерных наук",
        emails=[email],
        source_hash="hash",
    )
    project = Project.objects.create(
        title=f"Faculty match {uuid4().hex[:8]}",
        status=ProjectStatus.PUBLISHED,
        supervisor_name=full_name,
        supervisor_email=email,
        supervisor_department="ФКН",
    )

    match, changed = resolve_project_faculty_match(project)

    assert changed is True
    assert match.status == FacultyMatchStatus.CONFIRMED
    assert match.match_strategy == "email_exact"
    assert match.faculty_person is not None
    assert match.faculty_person.source_key == f"hse:email-{token}"


def test_resolve_project_faculty_match_marks_duplicate_name_ambiguous():
    token = uuid4().hex[:8]
    full_name = f"Петров Петр {token}"
    full_name_normalized = f"петров петр {token}"
    source_ids = (f"ambiguous-{token}-1", f"ambiguous-{token}-2")
    for source_id in source_ids:
        FacultyPerson.objects.create(
            source_key=f"hse:{source_id}",
            source_person_id=source_id,
            source_profile_url=f"https://www.hse.ru/org/persons/{source_id}",
            full_name=full_name,
            full_name_normalized=full_name_normalized,
            source_hash=f"hash-{source_id}",
        )
    project = Project.objects.create(
        title=f"Faculty ambiguous {uuid4().hex[:8]}",
        status=ProjectStatus.PUBLISHED,
        supervisor_name=full_name,
    )

    match, _ = resolve_project_faculty_match(project)

    assert match.status == FacultyMatchStatus.AMBIGUOUS
    assert sorted(match.candidate_person_ids) == [f"hse:{source_id}" for source_id in source_ids]
