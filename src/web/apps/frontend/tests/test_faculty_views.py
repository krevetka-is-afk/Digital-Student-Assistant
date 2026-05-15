from uuid import uuid4

import pytest
from apps.faculty.models import (
    FacultyCourse,
    FacultyPerson,
)
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()

pytestmark = pytest.mark.django_db


def _uid():
    return uuid4().hex[:8]


def _make_student():
    user = User.objects.create_user(username=f"stu-{_uid()}", password="pass")
    UserProfile.objects.create(user=user, role=UserRole.STUDENT)
    return user


def _make_cpprp():
    user = User.objects.create_user(username=f"cpprp-{_uid()}", password="pass")
    UserProfile.objects.create(user=user, role=UserRole.CPPRP)
    return user


def _make_faculty_person(*, is_stale=False, full_name=None):
    key = _uid()
    name = full_name or f"Person {key}"
    return FacultyPerson.objects.create(
        source_key=key,
        source_profile_url=f"https://example.com/person/{key}",
        full_name=name,
        full_name_normalized=name.lower(),
        source_hash=key,
        is_stale=is_stale,
    )


def _make_stale_faculty_person():
    return _make_faculty_person(is_stale=True)


class TestFacultyList:
    def test_unauth_redirects_to_login(self):
        response = Client().get(reverse("frontend:faculty_list"))
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_accessible_for_student(self):
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:faculty_list"))
        assert response.status_code == 200

    def test_accessible_for_cpprp(self):
        client = Client()
        client.force_login(_make_cpprp())
        response = client.get(reverse("frontend:faculty_list"))
        assert response.status_code == 200

    def test_shows_non_stale_person(self):
        person = _make_faculty_person()
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:faculty_list"))
        assert response.status_code == 200
        pks = {p.pk for p in response.context["page_obj"]}
        assert person.pk in pks

    def test_hides_stale_person(self):
        person = _make_faculty_person(is_stale=True)
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:faculty_list"))
        assert response.status_code == 200
        pks = {p.pk for p in response.context["page_obj"]}
        assert person.pk not in pks

    def test_search_by_name_finds_matching_person(self):
        unique_name = f"Профессор {_uid()}"
        person = _make_faculty_person(full_name=unique_name)
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:faculty_list"), {"q": unique_name[:10]})
        assert response.status_code == 200
        pks = {p.pk for p in response.context["page_obj"]}
        assert person.pk in pks

    def test_search_excludes_non_matching_person(self):
        _make_faculty_person(full_name=f"Иванов {_uid()}")
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:faculty_list"), {"q": "ZZZNOMATCHZZZ"})
        assert response.status_code == 200
        assert response.context["total"] == 0

    def test_context_has_query_key(self):
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:faculty_list"), {"q": "test"})
        assert response.status_code == 200
        assert response.context["query"] == "test"

    def test_context_total_matches_page_obj_count(self):
        _make_faculty_person()
        _make_faculty_person()
        _make_faculty_person(is_stale=True)
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:faculty_list"))
        assert response.status_code == 200
        ctx = response.context
        assert "total" in ctx
        assert "page_obj" in ctx
        assert ctx["total"] >= 2


class TestFacultyDetail:
    def test_unauth_redirects_to_login(self):
        person = _make_faculty_person()
        response = Client().get(
            reverse("frontend:faculty_detail", kwargs={"source_key": person.source_key})
        )
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_valid_source_key_returns_200(self):
        person = _make_faculty_person()
        client = Client()
        client.force_login(_make_student())
        response = client.get(
            reverse("frontend:faculty_detail", kwargs={"source_key": person.source_key})
        )
        assert response.status_code == 200

    def test_stale_person_returns_404(self):
        person = _make_faculty_person(is_stale=True)
        client = Client()
        client.force_login(_make_student())
        response = client.get(
            reverse("frontend:faculty_detail", kwargs={"source_key": person.source_key})
        )
        assert response.status_code == 404

    def test_unknown_source_key_returns_404(self):
        client = Client()
        client.force_login(_make_student())
        response = client.get(
            reverse("frontend:faculty_detail", kwargs={"source_key": "does-not-exist"})
        )
        assert response.status_code == 404

    def test_context_contains_person(self):
        person = _make_faculty_person()
        client = Client()
        client.force_login(_make_student())
        response = client.get(
            reverse("frontend:faculty_detail", kwargs={"source_key": person.source_key})
        )
        assert response.status_code == 200
        assert response.context["person"].pk == person.pk

    def test_context_contains_projects_and_courses_keys(self):
        person = _make_faculty_person()
        client = Client()
        client.force_login(_make_student())
        response = client.get(
            reverse("frontend:faculty_detail", kwargs={"source_key": person.source_key})
        )
        assert response.status_code == 200
        assert "projects" in response.context
        assert "courses" in response.context

    def test_courses_attached_to_person_appear_in_context(self):
        person = _make_faculty_person()
        course = FacultyCourse.objects.create(
            person=person,
            course_key=f"course-{_uid()}",
            title="Алгоритмы и структуры данных",
            source_hash=_uid(),
        )
        client = Client()
        client.force_login(_make_student())
        response = client.get(
            reverse("frontend:faculty_detail", kwargs={"source_key": person.source_key})
        )
        assert response.status_code == 200
        course_pks = {c.pk for c in response.context["courses"]}
        assert course.pk in course_pks

    def test_accessible_for_cpprp(self):
        person = _make_faculty_person()
        client = Client()
        client.force_login(_make_cpprp())
        response = client.get(
            reverse("frontend:faculty_detail", kwargs={"source_key": person.source_key})
        )
        assert response.status_code == 200
