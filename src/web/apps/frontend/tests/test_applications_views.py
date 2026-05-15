import json
from uuid import uuid4

import pytest
from apps.applications.models import Application, ApplicationStatus
from apps.projects.models import Project, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()

pytestmark = pytest.mark.django_db

_LONG_COMMENT = "К сожалению, ваша заявка не соответствует требованиям проекта по ряду критериев."
_LONG_MOTIVATION = "Я хочу участвовать в этом проекте, потому что обладаю необходимым опытом."


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


def _make_staff():
    return User.objects.create_user(username=f"staff-{_uid()}", password="pass", is_staff=True)


def _make_project(**kwargs):
    defaults = {"title": f"Project {_uid()}", "status": ProjectStatus.PUBLISHED, "team_size": 5}
    defaults.update(kwargs)
    return Project.objects.create(**defaults)


def _make_submitted_application(project, student):
    return Application.objects.create(
        project=project, applicant=student, status=ApplicationStatus.SUBMITTED
    )


class TestSubmitApplication:
    def test_unauthenticated_plain_returns_401_json(self):
        project = _make_project(owner=_make_customer())
        response = Client().post(
            reverse("frontend:submit_application", kwargs={"pk": project.pk}),
            {"motivation": "", "source": "card"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthenticated"
        assert "redirect" in data

    def test_unauthenticated_htmx_returns_204_redirect(self):
        project = _make_project(owner=_make_customer())
        response = Client().post(
            reverse("frontend:submit_application", kwargs={"pk": project.pk}),
            {"motivation": "", "source": "card"},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 204
        assert "HX-Redirect" in response

    def test_non_student_role_returns_403(self):
        customer = _make_customer()
        project = _make_project(owner=_make_customer())
        client = Client()
        client.force_login(customer)
        response = client.post(
            reverse("frontend:submit_application", kwargs={"pk": project.pk}),
            {"source": "card"},
        )
        assert response.status_code == 403
        assert Application.objects.filter(project=project, applicant=customer).count() == 0

    def test_non_student_role_returns_error_toast(self):
        customer = _make_customer()
        project = _make_project(owner=_make_customer())
        client = Client()
        client.force_login(customer)
        response = client.post(
            reverse("frontend:submit_application", kwargs={"pk": project.pk}),
            {"source": "card"},
        )
        trigger = json.loads(response["HX-Trigger"])
        assert trigger["showToast"]["type"] == "error"

    def test_project_not_found_returns_404(self):
        student = _make_student()
        client = Client()
        client.force_login(student)
        response = client.post(
            reverse("frontend:submit_application", kwargs={"pk": 999999}),
            {"source": "card"},
        )
        assert response.status_code == 404

    def test_motivation_too_short_returns_422_error_toast(self):
        student = _make_student()
        project = _make_project(owner=_make_customer())
        client = Client()
        client.force_login(student)
        response = client.post(
            reverse("frontend:submit_application", kwargs={"pk": project.pk}),
            {"source": "detail", "motivation": "short"},
        )
        assert response.status_code == 422
        trigger = json.loads(response["HX-Trigger"])
        assert trigger["showToast"]["type"] == "error"
        assert Application.objects.filter(project=project, applicant=student).count() == 0

    def test_full_team_project_returns_422_error_toast(self):
        student = _make_student()
        project = _make_project(
            owner=_make_customer(),
            status=ProjectStatus.STAFFED,
            team_size=1,
            accepted_participants_count=1,
        )
        client = Client()
        client.force_login(student)
        response = client.post(
            reverse("frontend:submit_application", kwargs={"pk": project.pk}),
            {"source": "card"},
        )
        assert response.status_code == 422
        trigger = json.loads(response["HX-Trigger"])
        assert trigger["showToast"]["type"] == "error"
        assert Application.objects.filter(project=project, applicant=student).count() == 0

    def test_success_creates_application_and_success_toast(self):
        student = _make_student()
        project = _make_project(owner=_make_customer())
        client = Client()
        client.force_login(student)
        response = client.post(
            reverse("frontend:submit_application", kwargs={"pk": project.pk}),
            {"source": "card", "motivation": ""},
        )
        assert response.status_code == 200
        assert Application.objects.filter(
            project=project, applicant=student, status=ApplicationStatus.SUBMITTED
        ).exists()
        trigger = json.loads(response["HX-Trigger"])
        assert trigger["showToast"]["type"] == "success"

    def test_already_applied_returns_info_toast_no_duplicate(self):
        student = _make_student()
        project = _make_project(owner=_make_customer())
        Application.objects.create(
            project=project, applicant=student, status=ApplicationStatus.SUBMITTED
        )
        client = Client()
        client.force_login(student)
        response = client.post(
            reverse("frontend:submit_application", kwargs={"pk": project.pk}),
            {"source": "card", "motivation": ""},
        )
        assert response.status_code == 200
        assert Application.objects.filter(project=project, applicant=student).count() == 1
        trigger = json.loads(response["HX-Trigger"])
        assert trigger["showToast"]["type"] == "info"


class TestApplicationList:
    def test_authenticated_redirects_to_projects_applications_tab(self):
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:application_list"))
        assert response.status_code == 302
        assert "tab=applications" in response["Location"]

    def test_unauthenticated_redirects_to_login(self):
        response = Client().get(reverse("frontend:application_list"))
        assert response.status_code == 302
        assert "/auth/" in response["Location"]


class TestProjectApplications:
    def test_owner_can_access(self):
        customer = _make_customer()
        project = _make_project(owner=customer)
        client = Client()
        client.force_login(customer)
        response = client.get(reverse("frontend:project_applications", kwargs={"pk": project.pk}))
        assert response.status_code == 200

    def test_non_owner_gets_404(self):
        project = _make_project(owner=_make_customer())
        client = Client()
        client.force_login(_make_customer())
        response = client.get(reverse("frontend:project_applications", kwargs={"pk": project.pk}))
        assert response.status_code == 404

    def test_unauthenticated_redirects_to_login(self):
        project = _make_project(owner=_make_customer())
        response = Client().get(reverse("frontend:project_applications", kwargs={"pk": project.pk}))
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_unknown_project_returns_404(self):
        client = Client()
        client.force_login(_make_customer())
        response = client.get(reverse("frontend:project_applications", kwargs={"pk": 999999}))
        assert response.status_code == 404

    def test_staff_can_access_any_project(self):
        project = _make_project(owner=_make_customer())
        client = Client()
        client.force_login(_make_staff())
        response = client.get(reverse("frontend:project_applications", kwargs={"pk": project.pk}))
        assert response.status_code == 200

    def test_status_filter_shows_only_matching(self):
        customer = _make_customer()
        student_a = _make_student()
        student_b = _make_student()
        project = _make_project(owner=customer)
        Application.objects.create(
            project=project, applicant=student_a, status=ApplicationStatus.SUBMITTED
        )
        Application.objects.create(
            project=project, applicant=student_b, status=ApplicationStatus.ACCEPTED
        )
        client = Client()
        client.force_login(customer)
        response = client.get(
            reverse("frontend:project_applications", kwargs={"pk": project.pk}),
            {"status": ApplicationStatus.SUBMITTED},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert student_a.username in content
        assert student_b.username not in content

    def test_invalid_status_filter_shows_all(self):
        customer = _make_customer()
        student = _make_student()
        project = _make_project(owner=customer)
        Application.objects.create(
            project=project, applicant=student, status=ApplicationStatus.SUBMITTED
        )
        client = Client()
        client.force_login(customer)
        response = client.get(
            reverse("frontend:project_applications", kwargs={"pk": project.pk}),
            {"status": "garbage_value"},
        )
        assert response.status_code == 200
        assert student.username in response.content.decode()

    def test_context_counts_and_total_are_correct(self):
        customer = _make_customer()
        project = _make_project(owner=customer)
        students = [_make_student() for _ in range(3)]
        Application.objects.create(
            project=project, applicant=students[0], status=ApplicationStatus.SUBMITTED
        )
        Application.objects.create(
            project=project, applicant=students[1], status=ApplicationStatus.ACCEPTED
        )
        Application.objects.create(
            project=project, applicant=students[2], status=ApplicationStatus.REJECTED
        )
        client = Client()
        client.force_login(customer)
        response = client.get(reverse("frontend:project_applications", kwargs={"pk": project.pk}))
        ctx = response.context
        assert ctx["counts"]["submitted"] == 1
        assert ctx["counts"]["accepted"] == 1
        assert ctx["counts"]["rejected"] == 1
        assert ctx["total_count"] == 3


class TestReviewApplicationView:
    def test_unauthenticated_redirects_to_login(self):
        project = _make_project(owner=_make_customer())
        app = _make_submitted_application(project, _make_student())
        response = Client().post(
            reverse("frontend:review_application", kwargs={"pk": app.pk}),
            {"decision": "accept", "comment": ""},
        )
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_get_method_not_allowed(self):
        customer = _make_customer()
        project = _make_project(owner=customer)
        app = _make_submitted_application(project, _make_student())
        client = Client()
        client.force_login(customer)
        response = client.get(reverse("frontend:review_application", kwargs={"pk": app.pk}))
        assert response.status_code == 405

    def test_unknown_application_returns_404(self):
        client = Client()
        client.force_login(_make_customer())
        response = client.post(
            reverse("frontend:review_application", kwargs={"pk": 999999}),
            {"decision": "accept", "comment": ""},
        )
        assert response.status_code == 404

    def test_accept_changes_status_and_shows_success_flash(self):
        customer = _make_customer()
        project = _make_project(owner=customer, team_size=3)
        app = _make_submitted_application(project, _make_student())
        client = Client()
        client.force_login(customer)
        response = client.post(
            reverse("frontend:review_application", kwargs={"pk": app.pk}),
            {"decision": "accept", "comment": ""},
        )
        assert response.status_code == 302
        app.refresh_from_db()
        assert app.status == ApplicationStatus.ACCEPTED
        assert any("принята" in str(m) for m in response.wsgi_request._messages)

    def test_reject_no_comment_keeps_submitted(self):
        customer = _make_customer()
        project = _make_project(owner=customer)
        app = _make_submitted_application(project, _make_student())
        client = Client()
        client.force_login(customer)
        client.post(
            reverse("frontend:review_application", kwargs={"pk": app.pk}),
            {"decision": "reject", "comment": ""},
        )
        app.refresh_from_db()
        assert app.status == ApplicationStatus.SUBMITTED

    def test_reject_short_comment_keeps_submitted(self):
        customer = _make_customer()
        project = _make_project(owner=customer)
        app = _make_submitted_application(project, _make_student())
        client = Client()
        client.force_login(customer)
        client.post(
            reverse("frontend:review_application", kwargs={"pk": app.pk}),
            {"decision": "reject", "comment": "слишком коротко"},
        )
        app.refresh_from_db()
        assert app.status == ApplicationStatus.SUBMITTED

    def test_reject_with_valid_comment_changes_status(self):
        customer = _make_customer()
        project = _make_project(owner=customer)
        app = _make_submitted_application(project, _make_student())
        client = Client()
        client.force_login(customer)
        response = client.post(
            reverse("frontend:review_application", kwargs={"pk": app.pk}),
            {"decision": "reject", "comment": _LONG_COMMENT},
        )
        assert response.status_code == 302
        app.refresh_from_db()
        assert app.status == ApplicationStatus.REJECTED
        assert any("отклонена" in str(m) for m in response.wsgi_request._messages)

    def test_non_owner_cannot_review(self):
        owner = _make_customer()
        project = _make_project(owner=owner)
        app = _make_submitted_application(project, _make_student())
        client = Client()
        client.force_login(_make_customer())
        response = client.post(
            reverse("frontend:review_application", kwargs={"pk": app.pk}),
            {"decision": "accept", "comment": ""},
        )
        assert response.status_code == 403
        app.refresh_from_db()
        assert app.status == ApplicationStatus.SUBMITTED

    def test_race_condition_already_reviewed_shows_flash(self):
        customer = _make_customer()
        project = _make_project(owner=customer, team_size=3)
        app = Application.objects.create(
            project=project, applicant=_make_student(), status=ApplicationStatus.ACCEPTED
        )
        client = Client()
        client.force_login(customer)
        response = client.post(
            reverse("frontend:review_application", kwargs={"pk": app.pk}),
            {"decision": "accept", "comment": ""},
        )
        assert response.status_code == 302
        app.refresh_from_db()
        assert app.status == ApplicationStatus.ACCEPTED
        assert any("статус" in str(m) for m in response.wsgi_request._messages)


class TestWithdrawApplicationView:
    def test_unauthenticated_redirects_to_login(self):
        project = _make_project(owner=_make_customer())
        app = _make_submitted_application(project, _make_student())
        response = Client().post(reverse("frontend:withdraw_application", kwargs={"pk": app.pk}))
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_get_method_not_allowed(self):
        student = _make_student()
        project = _make_project(owner=_make_customer())
        app = _make_submitted_application(project, student)
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:withdraw_application", kwargs={"pk": app.pk}))
        assert response.status_code == 405

    def test_unknown_application_returns_404(self):
        student = _make_student()
        client = Client()
        client.force_login(student)
        response = client.post(reverse("frontend:withdraw_application", kwargs={"pk": 999999}))
        assert response.status_code == 404

    def test_non_owner_gets_403(self):
        project = _make_project(owner=_make_customer())
        applicant = _make_student()
        other_student = _make_student()
        app = _make_submitted_application(project, applicant)
        client = Client()
        client.force_login(other_student)
        response = client.post(reverse("frontend:withdraw_application", kwargs={"pk": app.pk}))
        assert response.status_code == 403
        assert Application.objects.filter(pk=app.pk).exists()

    def test_non_submitted_status_redirects_with_flash(self):
        student = _make_student()
        project = _make_project(owner=_make_customer(), team_size=3)
        app = Application.objects.create(
            project=project, applicant=student, status=ApplicationStatus.ACCEPTED
        )
        client = Client()
        client.force_login(student)
        response = client.post(reverse("frontend:withdraw_application", kwargs={"pk": app.pk}))
        assert response.status_code == 302
        assert Application.objects.filter(pk=app.pk).exists()

    def test_success_deletes_application_and_redirects(self):
        student = _make_student()
        project = _make_project(owner=_make_customer())
        app = _make_submitted_application(project, student)
        app_pk = app.pk
        client = Client()
        client.force_login(student)
        response = client.post(reverse("frontend:withdraw_application", kwargs={"pk": app.pk}))
        assert response.status_code == 302
        assert not Application.objects.filter(pk=app_pk).exists()
        assert any("отозвана" in str(m) for m in response.wsgi_request._messages)


class TestEditApplicationView:
    def test_unauthenticated_get_redirects_to_login(self):
        project = _make_project(owner=_make_customer())
        app = _make_submitted_application(project, _make_student())
        response = Client().get(reverse("frontend:edit_application", kwargs={"pk": app.pk}))
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_unknown_application_returns_404(self):
        student = _make_student()
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:edit_application", kwargs={"pk": 999999}))
        assert response.status_code == 404

    def test_non_owner_get_returns_403(self):
        project = _make_project(owner=_make_customer())
        applicant = _make_student()
        other_student = _make_student()
        app = _make_submitted_application(project, applicant)
        client = Client()
        client.force_login(other_student)
        response = client.get(reverse("frontend:edit_application", kwargs={"pk": app.pk}))
        assert response.status_code == 403

    def test_non_submitted_status_redirects_with_flash(self):
        student = _make_student()
        project = _make_project(owner=_make_customer(), team_size=3)
        app = Application.objects.create(
            project=project, applicant=student, status=ApplicationStatus.ACCEPTED
        )
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:edit_application", kwargs={"pk": app.pk}))
        assert response.status_code == 302

    def test_get_renders_form_with_current_motivation(self):
        student = _make_student()
        project = _make_project(owner=_make_customer())
        app = Application.objects.create(
            project=project,
            applicant=student,
            status=ApplicationStatus.SUBMITTED,
            motivation=_LONG_MOTIVATION,
        )
        client = Client()
        client.force_login(student)
        response = client.get(reverse("frontend:edit_application", kwargs={"pk": app.pk}))
        assert response.status_code == 200
        assert _LONG_MOTIVATION in response.content.decode()

    def test_post_short_motivation_rerenders_form_without_saving(self):
        student = _make_student()
        project = _make_project(owner=_make_customer())
        app = Application.objects.create(
            project=project,
            applicant=student,
            status=ApplicationStatus.SUBMITTED,
            motivation=_LONG_MOTIVATION,
        )
        client = Client()
        client.force_login(student)
        response = client.post(
            reverse("frontend:edit_application", kwargs={"pk": app.pk}),
            {"motivation": "short"},
        )
        assert response.status_code == 200
        app.refresh_from_db()
        assert app.motivation == _LONG_MOTIVATION

    def test_post_empty_motivation_is_allowed(self):
        student = _make_student()
        project = _make_project(owner=_make_customer())
        app = Application.objects.create(
            project=project,
            applicant=student,
            status=ApplicationStatus.SUBMITTED,
            motivation=_LONG_MOTIVATION,
        )
        client = Client()
        client.force_login(student)
        response = client.post(
            reverse("frontend:edit_application", kwargs={"pk": app.pk}),
            {"motivation": ""},
        )
        assert response.status_code == 302
        app.refresh_from_db()
        assert app.motivation == ""

    def test_post_valid_motivation_updates_and_redirects(self):
        student = _make_student()
        project = _make_project(owner=_make_customer())
        app = _make_submitted_application(project, student)
        new_motivation = "Обновлённая мотивация длиной более тридцати символов."
        client = Client()
        client.force_login(student)
        response = client.post(
            reverse("frontend:edit_application", kwargs={"pk": app.pk}),
            {"motivation": new_motivation},
        )
        assert response.status_code == 302
        app.refresh_from_db()
        assert app.motivation == new_motivation
        assert any("обновлена" in str(m).lower() for m in response.wsgi_request._messages)
