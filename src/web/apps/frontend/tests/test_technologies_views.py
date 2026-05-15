from uuid import uuid4

import pytest
from apps.projects.models import Technology, TechnologyStatus
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


def _make_technology(*, status=TechnologyStatus.PENDING, name=None):
    n = name or f"tech-{_uid()}"
    return Technology.objects.create(name=n, normalized_name=n, status=status)


class TestTechnologyList:
    def test_unauth_redirects_to_login(self):
        response = Client().get(reverse("frontend:technology_list"))
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_accessible_for_student(self):
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:technology_list"))
        assert response.status_code == 200

    def test_shows_approved_technology(self):
        tech = _make_technology(status=TechnologyStatus.APPROVED)
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:technology_list"))
        assert response.status_code == 200
        approved_pks = {t.pk for t in response.context["approved_technologies"]}
        assert tech.pk in approved_pks

    def test_pending_hidden_from_non_moderator(self):
        _make_technology(status=TechnologyStatus.PENDING)
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:technology_list"))
        assert response.status_code == 200
        assert response.context["pending_technologies"] == []

    def test_pending_visible_for_moderator(self):
        tech = _make_technology(status=TechnologyStatus.PENDING)
        client = Client()
        client.force_login(_make_cpprp())
        response = client.get(reverse("frontend:technology_list"))
        assert response.status_code == 200
        pending_pks = {t.pk for t in response.context["pending_technologies"]}
        assert tech.pk in pending_pks

    def test_total_approved_count_in_context(self):
        _make_technology(status=TechnologyStatus.APPROVED)
        _make_technology(status=TechnologyStatus.APPROVED)
        _make_technology(status=TechnologyStatus.PENDING)
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:technology_list"))
        assert response.status_code == 200
        assert response.context["total_approved"] >= 2
        assert response.context["total_approved"] == len(
            list(response.context["approved_technologies"])
        )


class TestTechnologyModerate:
    def test_unauth_redirects_to_login(self):
        tech = _make_technology()
        response = Client().post(
            reverse("frontend:technology_moderate", kwargs={"pk": tech.pk}),
            {"action": "approve"},
        )
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_get_method_not_allowed(self):
        tech = _make_technology()
        client = Client()
        client.force_login(_make_cpprp())
        response = client.get(reverse("frontend:technology_moderate", kwargs={"pk": tech.pk}))
        assert response.status_code == 405

    def test_forbidden_for_student(self):
        tech = _make_technology()
        client = Client()
        client.force_login(_make_student())
        response = client.post(
            reverse("frontend:technology_moderate", kwargs={"pk": tech.pk}),
            {"action": "approve"},
        )
        assert response.status_code == 403
        tech.refresh_from_db()
        assert tech.status == TechnologyStatus.PENDING

    def test_approve_changes_status(self):
        tech = _make_technology(status=TechnologyStatus.PENDING)
        client = Client()
        client.force_login(_make_cpprp())
        response = client.post(
            reverse("frontend:technology_moderate", kwargs={"pk": tech.pk}),
            {"action": "approve"},
        )
        assert response.status_code == 302
        tech.refresh_from_db()
        assert tech.status == TechnologyStatus.APPROVED

    def test_reject_changes_status(self):
        tech = _make_technology(status=TechnologyStatus.PENDING)
        client = Client()
        client.force_login(_make_cpprp())
        response = client.post(
            reverse("frontend:technology_moderate", kwargs={"pk": tech.pk}),
            {"action": "reject"},
        )
        assert response.status_code == 302
        tech.refresh_from_db()
        assert tech.status == TechnologyStatus.REJECTED

    def test_unknown_action_flashes_error_no_status_change(self):
        tech = _make_technology(status=TechnologyStatus.PENDING)
        client = Client()
        client.force_login(_make_cpprp())
        response = client.post(
            reverse("frontend:technology_moderate", kwargs={"pk": tech.pk}),
            {"action": "garbage"},
        )
        assert response.status_code == 302
        tech.refresh_from_db()
        assert tech.status == TechnologyStatus.PENDING
        stored = list(response.wsgi_request._messages)
        assert any(m.level_tag == "error" for m in stored)

    def test_already_approved_returns_404(self):
        tech = _make_technology(status=TechnologyStatus.APPROVED)
        client = Client()
        client.force_login(_make_cpprp())
        response = client.post(
            reverse("frontend:technology_moderate", kwargs={"pk": tech.pk}),
            {"action": "approve"},
        )
        assert response.status_code == 404
