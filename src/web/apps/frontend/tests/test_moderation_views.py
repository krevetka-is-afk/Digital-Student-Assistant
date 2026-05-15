from uuid import uuid4

import pytest
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from apps.projects.transitions import MODERATION_COMMENT_MIN_LEN
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()

pytestmark = pytest.mark.django_db

_LONG_COMMENT = (
    "Проект не соответствует требованиям программы. Необходимо доработать описание, "
    "добавить конкретные цели, критерии отбора участников и ожидаемые результаты работы."
)
assert len(_LONG_COMMENT) >= MODERATION_COMMENT_MIN_LEN


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


def _make_staff():
    return User.objects.create_user(username=f"staff-{_uid()}", password="pass", is_staff=True)


def _make_project(owner, *, status=ProjectStatus.ON_MODERATION, **kwargs):
    defaults = {"title": f"Project {_uid()}", "team_size": 3}
    defaults.update(kwargs)
    return Project.objects.create(owner=owner, status=status, **defaults)


class TestModerationList:
    def test_unauth_redirects_to_login(self):
        client = Client()
        response = client.get(reverse("frontend:moderation_list"))
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_forbidden_for_student(self):
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:moderation_list"))
        assert response.status_code == 403

    def test_forbidden_for_customer(self):
        client = Client()
        client.force_login(_make_customer())
        response = client.get(reverse("frontend:moderation_list"))
        assert response.status_code == 403

    def test_accessible_for_cpprp(self):
        client = Client()
        client.force_login(_make_cpprp())
        response = client.get(reverse("frontend:moderation_list"))
        assert response.status_code == 200
        assert "Очередь модерации" in response.content.decode()

    def test_accessible_for_staff(self):
        client = Client()
        client.force_login(_make_staff())
        response = client.get(reverse("frontend:moderation_list"))
        assert response.status_code == 200

    def test_shows_pending_projects_not_draft(self):
        cpprp = _make_cpprp()
        customer = _make_customer()
        pending = _make_project(customer)
        draft = _make_project(customer, status=ProjectStatus.DRAFT, title=f"Draft {_uid()}")
        client = Client()
        client.force_login(cpprp)
        response = client.get(reverse("frontend:moderation_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert pending.title in content
        assert draft.title not in content

    def test_queue_count_equals_on_moderation_projects(self):
        cpprp = _make_cpprp()
        customer = _make_customer()
        _make_project(customer)
        _make_project(customer)
        _make_project(customer, status=ProjectStatus.DRAFT)
        client = Client()
        client.force_login(cpprp)
        response = client.get(reverse("frontend:moderation_list"))
        assert response.status_code == 200
        assert response.context["queue_count"] >= 2


class TestModerateProjectDecide:
    def test_unauth_redirects_to_login(self):
        customer = _make_customer()
        project = _make_project(customer)
        response = Client().post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
            {"decision": "approve", "comment": ""},
        )
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_get_method_not_allowed(self):
        cpprp = _make_cpprp()
        customer = _make_customer()
        project = _make_project(customer)
        client = Client()
        client.force_login(cpprp)
        response = client.get(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk})
        )
        assert response.status_code == 405

    def test_project_not_found_returns_404(self):
        cpprp = _make_cpprp()
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": 999999}),
            {"decision": "approve", "comment": ""},
        )
        assert response.status_code == 404

    def test_forbidden_for_student(self):
        customer = _make_customer()
        project = _make_project(customer)
        client = Client()
        client.force_login(_make_student())
        response = client.post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
            {"decision": "approve", "comment": ""},
        )
        assert response.status_code == 403
        project.refresh_from_db()
        assert project.status == ProjectStatus.ON_MODERATION

    def test_forbidden_for_customer(self):
        customer = _make_customer()
        project = _make_project(customer)
        client = Client()
        client.force_login(customer)
        response = client.post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
            {"decision": "approve", "comment": ""},
        )
        assert response.status_code == 403
        project.refresh_from_db()
        assert project.status == ProjectStatus.ON_MODERATION

    def test_staff_can_approve(self):
        staff = _make_staff()
        customer = _make_customer()
        project = _make_project(customer)
        client = Client()
        client.force_login(staff)
        response = client.post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
            {"decision": "approve", "comment": ""},
        )
        assert response.status_code == 302
        project.refresh_from_db()
        assert project.status == ProjectStatus.PUBLISHED
        assert project.moderated_by == staff

    def test_approve_publishes_project(self):
        cpprp = _make_cpprp()
        customer = _make_customer()
        project = _make_project(customer)
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
            {"decision": "approve", "comment": ""},
        )
        assert response.status_code == 302
        project.refresh_from_db()
        assert project.status == ProjectStatus.PUBLISHED
        stored = list(response.wsgi_request._messages)
        assert any("опубликован" in str(m) for m in stored)

    def test_reject_with_long_comment_rejects_project(self):
        cpprp = _make_cpprp()
        customer = _make_customer()
        project = _make_project(customer, source_type=ProjectSourceType.MANUAL)
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
            {"decision": "reject", "comment": _LONG_COMMENT},
        )
        assert response.status_code == 302
        project.refresh_from_db()
        assert project.status == ProjectStatus.REJECTED
        stored = list(response.wsgi_request._messages)
        assert any("отклонён" in str(m) for m in stored)

    def test_reject_initiative_goes_to_revision_requested(self):
        cpprp = _make_cpprp()
        customer = _make_customer()
        project = _make_project(customer, source_type=ProjectSourceType.INITIATIVE)
        client = Client()
        client.force_login(cpprp)
        client.post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
            {"decision": "reject", "comment": _LONG_COMMENT},
        )
        project.refresh_from_db()
        assert project.status == ProjectStatus.REVISION_REQUESTED

    def test_invalid_decision_flashes_error_no_status_change(self):
        cpprp = _make_cpprp()
        customer = _make_customer()
        project = _make_project(customer)
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
            {"decision": "garbage", "comment": ""},
        )
        assert response.status_code == 302
        project.refresh_from_db()
        assert project.status == ProjectStatus.ON_MODERATION
        stored = list(response.wsgi_request._messages)
        assert any(m.level_tag == "error" for m in stored)

    def test_reject_no_comment_flashes_error(self):
        cpprp = _make_cpprp()
        customer = _make_customer()
        project = _make_project(customer)
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
            {"decision": "reject", "comment": ""},
        )
        assert response.status_code == 302
        project.refresh_from_db()
        assert project.status == ProjectStatus.ON_MODERATION
        stored = list(response.wsgi_request._messages)
        assert any(m.level_tag == "error" for m in stored)

    def test_reject_comment_too_short_flashes_error(self):
        cpprp = _make_cpprp()
        customer = _make_customer()
        project = _make_project(customer)
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
            {"decision": "reject", "comment": "слишком короткий комментарий"},
        )
        assert response.status_code == 302
        project.refresh_from_db()
        assert project.status == ProjectStatus.ON_MODERATION
        stored = list(response.wsgi_request._messages)
        assert any(m.level_tag == "error" for m in stored)

    def test_race_condition_already_moderated(self):
        cpprp = _make_cpprp()
        customer = _make_customer()
        project = _make_project(customer, status=ProjectStatus.PUBLISHED)
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
            {"decision": "approve", "comment": ""},
        )
        assert response.status_code == 302
        project.refresh_from_db()
        assert project.status == ProjectStatus.PUBLISHED
        stored = list(response.wsgi_request._messages)
        assert any(m.level_tag == "error" for m in stored)
