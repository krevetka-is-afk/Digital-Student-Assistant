from uuid import uuid4

import pytest
from apps.account.models import DeadlineAudience, DocumentTemplate, PlatformDeadline
from apps.applications.models import Application, ApplicationStatus
from apps.projects.models import Project, ProjectStatus
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


def _make_customer():
    user = User.objects.create_user(username=f"cust-{_uid()}", password="pass")
    UserProfile.objects.create(user=user, role=UserRole.CUSTOMER)
    return user


def _make_cpprp():
    user = User.objects.create_user(username=f"cpprp-{_uid()}", password="pass")
    UserProfile.objects.create(user=user, role=UserRole.CPPRP)
    return user


def _make_project(**kwargs):
    defaults = {"title": f"Project {_uid()}", "status": ProjectStatus.PUBLISHED, "team_size": 3}
    defaults.update(kwargs)
    return Project.objects.create(**defaults)


class TestStudentOverview:
    def test_unauth_redirects_to_login(self):
        response = Client().get(reverse("frontend:student_overview"))
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_forbidden_for_customer(self):
        client = Client()
        client.force_login(_make_customer())
        response = client.get(reverse("frontend:student_overview"))
        assert response.status_code == 302

    def test_forbidden_for_cpprp(self):
        client = Client()
        client.force_login(_make_cpprp())
        response = client.get(reverse("frontend:student_overview"))
        assert response.status_code == 302

    def test_accessible_for_student(self):
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:student_overview"))
        assert response.status_code == 200

    def test_context_has_correct_counters(self):
        student = _make_student()
        project = _make_project()
        Application.objects.create(
            project=project,
            applicant=student,
            status=ApplicationStatus.SUBMITTED,
        )
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:student_overview"))
        assert response.status_code == 200
        counters = response.context["counters"]
        assert counters["total"] >= 1
        assert counters["submitted"] >= 1

    def test_context_has_recent_apps(self):
        student = _make_student()
        project = _make_project()
        Application.objects.create(
            project=project,
            applicant=student,
            status=ApplicationStatus.SUBMITTED,
        )
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:student_overview"))
        assert response.status_code == 200
        recent = response.context["recent_apps"]
        assert len(recent) >= 1

    def test_context_has_fav_projects(self):
        student = _make_student()
        project = _make_project()
        student.profile.set_favorite_project_ids([project.pk])
        student.profile.save(update_fields=["favorite_project_ids"])
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:student_overview"))
        assert response.status_code == 200
        fav_projects = response.context["fav_projects"]
        assert any(p.pk == project.pk for p in fav_projects)

    def test_context_has_active_student_deadlines(self):
        student = _make_student()
        dl = PlatformDeadline.objects.create(
            slug=f"dl-{_uid()}",
            title="Test Deadline",
            audience=DeadlineAudience.STUDENT,
            is_active=True,
        )
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:student_overview"))
        assert response.status_code == 200
        deadlines = response.context["deadlines"]
        assert any(d.pk == dl.pk for d in deadlines)

    def test_inactive_deadline_not_shown(self):
        student = _make_student()
        PlatformDeadline.objects.create(
            slug=f"dl-{_uid()}",
            title="Inactive Deadline",
            audience=DeadlineAudience.STUDENT,
            is_active=False,
        )
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:student_overview"))
        assert response.status_code == 200
        deadlines = response.context["deadlines"]
        assert all(d.is_active for d in deadlines)

    def test_context_has_active_student_templates(self):
        student = _make_student()
        tpl = DocumentTemplate.objects.create(
            slug=f"tpl-{_uid()}",
            title="Test Template",
            url="https://example.com/template.docx",
            audience=DeadlineAudience.STUDENT,
            is_active=True,
        )
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:student_overview"))
        assert response.status_code == 200
        templates = response.context["templates"]
        assert any(t.pk == tpl.pk for t in templates)

    def test_cpprp_audience_deadline_not_shown_to_student(self):
        student = _make_student()
        PlatformDeadline.objects.create(
            slug=f"dl-{_uid()}",
            title="CPPRP Only Deadline",
            audience=DeadlineAudience.CPPRP,
            is_active=True,
        )
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:student_overview"))
        assert response.status_code == 200
        deadlines = response.context["deadlines"]
        for d in deadlines:
            assert d.audience in (DeadlineAudience.STUDENT, DeadlineAudience.GLOBAL)

    def test_global_deadline_shown_to_student(self):
        student = _make_student()
        dl = PlatformDeadline.objects.create(
            slug=f"dl-{_uid()}",
            title="Global Deadline",
            audience=DeadlineAudience.GLOBAL,
            is_active=True,
        )
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:student_overview"))
        assert any(d.pk == dl.pk for d in response.context["deadlines"])

    def test_favorites_count_in_counters(self):
        student = _make_student()
        p1 = _make_project()
        p2 = _make_project()
        student.profile.set_favorite_project_ids([p1.pk, p2.pk])
        student.profile.save(update_fields=["favorite_project_ids"])
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:student_overview"))
        assert response.context["counters"]["favorites"] == 2

    def test_recent_apps_capped_at_limit(self):
        from apps.frontend.views.student import _RECENT_APPS

        student = _make_student()
        for _ in range(_RECENT_APPS + 2):
            Application.objects.create(
                project=_make_project(),
                applicant=student,
                status=ApplicationStatus.SUBMITTED,
            )
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:student_overview"))
        assert len(response.context["recent_apps"]) == _RECENT_APPS
        assert response.context["counters"]["total"] == _RECENT_APPS + 2
