from uuid import uuid4

import pytest
from apps.account.models import DeadlineAudience, DocumentTemplate, PlatformDeadline
from apps.applications.models import Application, ApplicationStatus
from apps.projects.models import Project, ProjectStatus
from apps.users.models import (
    ExternalAccessAllowlist,
    ExternalAccessRequest,
    ExternalAccessRequestStatus,
    UserProfile,
    UserRole,
)
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


def _make_project(owner=None, **kwargs):
    if owner is None:
        owner = _make_customer()
    defaults = {"title": f"Project {_uid()}", "status": ProjectStatus.PUBLISHED, "team_size": 3}
    defaults.update(kwargs)
    return Project.objects.create(owner=owner, **defaults)


class TestCpprpDashboard:
    def test_unauth_redirects_to_login(self):
        response = Client().get(reverse("frontend:cpprp_dashboard"))
        assert response.status_code == 302
        assert "/auth/" in response["Location"]

    def test_forbidden_for_student(self):
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:cpprp_dashboard"))
        assert response.status_code in (302, 403)

    def test_forbidden_for_customer(self):
        client = Client()
        client.force_login(_make_customer())
        response = client.get(reverse("frontend:cpprp_dashboard"))
        assert response.status_code in (302, 403)

    def test_accessible_for_cpprp(self):
        client = Client()
        client.force_login(_make_cpprp())
        response = client.get(reverse("frontend:cpprp_dashboard"))
        assert response.status_code == 200

    def test_context_has_project_counts(self):
        customer = _make_customer()
        _make_project(customer, status=ProjectStatus.PUBLISHED)
        _make_project(customer, status=ProjectStatus.DRAFT)
        client = Client()
        client.force_login(_make_cpprp())
        response = client.get(reverse("frontend:cpprp_dashboard"))
        assert response.status_code == 200
        counts = response.context["project_counts"]
        assert counts[ProjectStatus.PUBLISHED] >= 1
        assert counts[ProjectStatus.DRAFT] >= 1

    def test_context_has_app_totals(self):
        student = _make_student()
        project = _make_project()
        Application.objects.create(
            project=project,
            applicant=student,
            status=ApplicationStatus.SUBMITTED,
        )
        client = Client()
        client.force_login(_make_cpprp())
        response = client.get(reverse("frontend:cpprp_dashboard"))
        assert response.status_code == 200
        totals = response.context["app_totals"]
        assert totals["total"] >= 1
        assert totals["submitted"] >= 1


class TestCpprpDeadlineCRUD:
    def test_create_deadline_success(self):
        cpprp = _make_cpprp()
        client = Client()
        client.force_login(cpprp)
        slug = f"dl-{_uid()}"
        response = client.post(
            reverse("frontend:cpprp_deadline_create"),
            {
                "slug": slug,
                "title": "Дедлайн заявок",
                "audience": DeadlineAudience.STUDENT,
            },
        )
        assert response.status_code == 302
        assert "?tab=deadlines" in response["Location"]
        assert PlatformDeadline.objects.filter(slug=slug).exists()

    def test_create_deadline_duplicate_slug_flashes_error(self):
        cpprp = _make_cpprp()
        slug = f"dl-{_uid()}"
        PlatformDeadline.objects.create(
            slug=slug,
            title="Existing",
            audience=DeadlineAudience.GLOBAL,
        )
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:cpprp_deadline_create"),
            {"slug": slug, "title": "Duplicate", "audience": DeadlineAudience.GLOBAL},
        )
        assert response.status_code == 302
        stored = list(response.wsgi_request._messages)
        assert any(m.level_tag == "error" for m in stored)
        assert PlatformDeadline.objects.filter(slug=slug).count() == 1

    def test_create_deadline_invalid_form_flashes_error(self):

        cpprp = _make_cpprp()
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:cpprp_deadline_create"),
            {"slug": f"sl-{_uid()}", "audience": DeadlineAudience.GLOBAL},
        )
        assert response.status_code == 302
        stored = list(response.wsgi_request._messages)
        assert any(m.level_tag == "error" for m in stored)

    def test_toggle_deadline_deactivates(self):
        cpprp = _make_cpprp()
        dl = PlatformDeadline.objects.create(
            slug=f"dl-{_uid()}",
            title="Toggle me",
            audience=DeadlineAudience.GLOBAL,
            is_active=True,
        )
        client = Client()
        client.force_login(cpprp)
        response = client.post(reverse("frontend:cpprp_deadline_toggle", kwargs={"pk": dl.pk}))
        assert response.status_code == 302
        dl.refresh_from_db()
        assert dl.is_active is False

    def test_toggle_deadline_activates(self):
        cpprp = _make_cpprp()
        dl = PlatformDeadline.objects.create(
            slug=f"dl-{_uid()}",
            title="Activate me",
            audience=DeadlineAudience.GLOBAL,
            is_active=False,
        )
        client = Client()
        client.force_login(cpprp)
        client.post(reverse("frontend:cpprp_deadline_toggle", kwargs={"pk": dl.pk}))
        dl.refresh_from_db()
        assert dl.is_active is True

    def test_delete_deadline(self):
        cpprp = _make_cpprp()
        dl = PlatformDeadline.objects.create(
            slug=f"dl-{_uid()}",
            title="Delete me",
            audience=DeadlineAudience.GLOBAL,
        )
        pk = dl.pk
        client = Client()
        client.force_login(cpprp)
        response = client.post(reverse("frontend:cpprp_deadline_delete", kwargs={"pk": pk}))
        assert response.status_code == 302
        assert not PlatformDeadline.objects.filter(pk=pk).exists()


class TestCpprpTemplateCRUD:
    def test_create_template_success(self):
        cpprp = _make_cpprp()
        client = Client()
        client.force_login(cpprp)
        slug = f"tpl-{_uid()}"
        response = client.post(
            reverse("frontend:cpprp_template_create"),
            {
                "slug": slug,
                "title": "Заявление студента",
                "url": "https://example.com/template.docx",
                "audience": DeadlineAudience.STUDENT,
            },
        )
        assert response.status_code == 302
        assert "?tab=templates" in response["Location"]
        assert DocumentTemplate.objects.filter(slug=slug).exists()

    def test_create_template_duplicate_slug_flashes_error(self):
        cpprp = _make_cpprp()
        slug = f"tpl-{_uid()}"
        DocumentTemplate.objects.create(
            slug=slug,
            title="Existing",
            url="https://example.com/a.docx",
            audience=DeadlineAudience.GLOBAL,
        )
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:cpprp_template_create"),
            {
                "slug": slug,
                "title": "Duplicate",
                "url": "https://example.com/b.docx",
                "audience": DeadlineAudience.GLOBAL,
            },
        )
        assert response.status_code == 302
        stored = list(response.wsgi_request._messages)
        assert any(m.level_tag == "error" for m in stored)
        assert DocumentTemplate.objects.filter(slug=slug).count() == 1

    def test_toggle_template_deactivates(self):
        cpprp = _make_cpprp()
        tpl = DocumentTemplate.objects.create(
            slug=f"tpl-{_uid()}",
            title="Toggle me",
            url="https://example.com/t.docx",
            audience=DeadlineAudience.GLOBAL,
            is_active=True,
        )
        client = Client()
        client.force_login(cpprp)
        response = client.post(reverse("frontend:cpprp_template_toggle", kwargs={"pk": tpl.pk}))
        assert response.status_code == 302
        tpl.refresh_from_db()
        assert tpl.is_active is False

    def test_delete_template(self):
        cpprp = _make_cpprp()
        tpl = DocumentTemplate.objects.create(
            slug=f"tpl-{_uid()}",
            title="Delete me",
            url="https://example.com/d.docx",
            audience=DeadlineAudience.GLOBAL,
        )
        pk = tpl.pk
        client = Client()
        client.force_login(cpprp)
        response = client.post(reverse("frontend:cpprp_template_delete", kwargs={"pk": pk}))
        assert response.status_code == 302
        assert not DocumentTemplate.objects.filter(pk=pk).exists()


class TestCpprpExport:
    def test_export_projects_returns_csv(self):
        _make_project()
        client = Client()
        client.force_login(_make_cpprp())
        response = client.get(reverse("frontend:cpprp_export_projects"))
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]
        assert "attachment" in response["Content-Disposition"]
        content = response.content.decode("utf-8-sig")
        assert "id" in content
        assert "title" in content

    def test_export_applications_returns_csv(self):
        student = _make_student()
        project = _make_project()
        Application.objects.create(
            project=project,
            applicant=student,
            status=ApplicationStatus.SUBMITTED,
        )
        client = Client()
        client.force_login(_make_cpprp())
        response = client.get(reverse("frontend:cpprp_export_applications"))
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]
        content = response.content.decode("utf-8-sig")
        assert "project_id" in content
        assert "applicant_id" in content

    def test_export_forbidden_for_student(self):
        client = Client()
        client.force_login(_make_student())
        response = client.get(reverse("frontend:cpprp_export_projects"))
        assert response.status_code in (302, 403)


class TestCpprpExternalAccess:
    def test_bulk_add_creates_new_allowlist_entry(self):
        cpprp = _make_cpprp()
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:cpprp_external_allowlist_bulk_add"),
            {"emails": "newuser@example.com", "allowed_role": UserRole.CUSTOMER},
        )
        assert response.status_code == 302
        assert "?tab=external-access" in response["Location"]
        assert ExternalAccessAllowlist.objects.filter(email="newuser@example.com").exists()

    def test_bulk_add_reactivates_and_updates_existing_entry(self):
        cpprp = _make_cpprp()
        ExternalAccessAllowlist.objects.create(
            email="existing@example.com",
            allowed_role=UserRole.CUSTOMER,
            is_active=False,
        )
        client = Client()
        client.force_login(cpprp)
        client.post(
            reverse("frontend:cpprp_external_allowlist_bulk_add"),
            {"emails": "existing@example.com", "allowed_role": UserRole.CUSTOMER},
        )
        entry = ExternalAccessAllowlist.objects.get(email="existing@example.com")
        assert entry.is_active is True
        assert entry.approved_by == cpprp

    def test_approve_request_updates_status_and_creates_allowlist_entry(self):
        cpprp = _make_cpprp()
        req = ExternalAccessRequest.objects.create(
            email="pending@example.com",
            requested_role=UserRole.CUSTOMER,
        )
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:cpprp_external_request_approve", kwargs={"pk": req.pk})
        )
        assert response.status_code == 302
        req.refresh_from_db()
        assert req.status == ExternalAccessRequestStatus.APPROVED
        assert req.reviewed_by_id == cpprp.pk
        assert ExternalAccessAllowlist.objects.filter(email="pending@example.com").exists()

    def test_reject_request_updates_status(self):
        cpprp = _make_cpprp()
        req = ExternalAccessRequest.objects.create(
            email="toreject@example.com",
            requested_role=UserRole.CUSTOMER,
        )
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:cpprp_external_request_reject", kwargs={"pk": req.pk})
        )
        assert response.status_code == 302
        req.refresh_from_db()
        assert req.status == ExternalAccessRequestStatus.REJECTED
        assert req.reviewed_by_id == cpprp.pk

    def test_toggle_allowlist_deactivates_active_entry(self):
        cpprp = _make_cpprp()
        entry = ExternalAccessAllowlist.objects.create(
            email="toggle@example.com",
            allowed_role=UserRole.CUSTOMER,
            is_active=True,
        )
        client = Client()
        client.force_login(cpprp)
        response = client.post(
            reverse("frontend:cpprp_external_allowlist_toggle", kwargs={"pk": entry.pk})
        )
        assert response.status_code == 302
        entry.refresh_from_db()
        assert entry.is_active is False

    def test_external_access_forbidden_for_student(self):
        req = ExternalAccessRequest.objects.create(
            email="blocked@example.com",
            requested_role=UserRole.CUSTOMER,
        )
        client = Client()
        client.force_login(_make_student())
        response = client.post(
            reverse("frontend:cpprp_external_request_approve", kwargs={"pk": req.pk})
        )
        assert response.status_code in (302, 403)
        req.refresh_from_db()
        assert req.status == ExternalAccessRequestStatus.PENDING
