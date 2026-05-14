from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from apps.base.admin_unfold import UnfoldModelAdmin
from apps.projects.admin import ProjectAdmin, ProjectAdminForm
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from apps.users.admin import (
    EmailVerificationCodeAdmin,
    ExternalAccessAllowlistAdmin,
    ExternalAccessRequestAdmin,
    GroupAdmin,
    UserAdmin,
    UserProfileAdmin,
)
from apps.users.models import (
    EmailVerificationCode,
    ExternalAccessAllowlist,
    ExternalAccessRequest,
    UserProfile,
)
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.test import RequestFactory
from django.urls import reverse


def _project_admin() -> ProjectAdmin:
    return admin.site._registry[Project]


def _uid() -> str:
    return uuid4().hex[:8]


def test_project_registered_in_admin():
    assert Project in admin.site._registry
    assert isinstance(_project_admin(), ProjectAdmin)
    assert isinstance(_project_admin(), UnfoldModelAdmin)


def test_dsa_admins_use_unfold_base():
    assert isinstance(admin.site._registry[UserProfile], UserProfileAdmin)
    assert isinstance(admin.site._registry[EmailVerificationCode], EmailVerificationCodeAdmin)
    assert isinstance(admin.site._registry[ExternalAccessAllowlist], ExternalAccessAllowlistAdmin)
    assert isinstance(admin.site._registry[ExternalAccessRequest], ExternalAccessRequestAdmin)
    assert isinstance(admin.site._registry[UserProfile], UnfoldModelAdmin)
    assert isinstance(admin.site._registry[EmailVerificationCode], UnfoldModelAdmin)
    assert isinstance(admin.site._registry[ExternalAccessAllowlist], UnfoldModelAdmin)
    assert isinstance(admin.site._registry[ExternalAccessRequest], UnfoldModelAdmin)


def test_standard_auth_admins_are_restyled():
    assert isinstance(admin.site._registry[User], UserAdmin)
    assert isinstance(admin.site._registry[Group], GroupAdmin)
    assert isinstance(admin.site._registry[User], UnfoldModelAdmin)
    assert isinstance(admin.site._registry[Group], UnfoldModelAdmin)


def test_project_admin_list_and_filter_config():
    project_admin = _project_admin()

    assert {"title", "status", "owner", "updated_at"}.issubset(project_admin.list_display)
    assert {"status", "owner"}.issubset(project_admin.list_filter)
    assert "title" in project_admin.search_fields
    assert "description" in project_admin.search_fields


def test_project_admin_fast_manual_entry_defaults():
    project_admin = _project_admin()

    assert project_admin.autocomplete_fields == ("owner",)
    assert project_admin.list_select_related == ("owner",)
    assert project_admin.readonly_fields == ("created_at", "updated_at")
    assert project_admin.list_per_page == 50


def test_project_admin_uses_readable_fieldsets():
    project_admin = _project_admin()

    assert [name for name, _ in project_admin.fieldsets] == [
        "Core information",
        "Source and tags",
        "Additional metadata",
        "System fields",
    ]


def test_project_admin_form_help_texts_for_json_fields():
    form = ProjectAdminForm()

    assert "JSON array" in form.fields["tech_tags"].help_text
    assert "Leave empty unless needed" in form.fields["extra_data"].help_text


def test_project_admin_actions_registered():
    project_admin = _project_admin()

    assert "publish_selected" in project_admin.actions
    assert "archive_selected" in project_admin.actions
    assert "export_selected_as_csv" in project_admin.actions
    assert "export_selected_as_epp_xlsx" in project_admin.actions


def test_project_admin_publish_action_updates_status():
    project_admin = _project_admin()
    message_user = MagicMock()
    setattr(project_admin, "message_user", message_user)
    request = MagicMock()
    queryset = MagicMock()
    queryset.exclude.return_value.update.return_value = 2

    project_admin.publish_selected(request, queryset)

    queryset.exclude.assert_called_once_with(status=ProjectStatus.PUBLISHED)
    queryset.exclude.return_value.update.assert_called_once_with(status=ProjectStatus.PUBLISHED)
    message_user.assert_called_once_with(request, "Published 2 project(s).")


def test_project_admin_archive_action_updates_status():
    project_admin = _project_admin()
    message_user = MagicMock()
    setattr(project_admin, "message_user", message_user)
    request = MagicMock()
    queryset = MagicMock()
    queryset.exclude.return_value.update.return_value = 3

    project_admin.archive_selected(request, queryset)

    queryset.exclude.assert_called_once_with(status=ProjectStatus.ARCHIVED)
    queryset.exclude.return_value.update.assert_called_once_with(status=ProjectStatus.ARCHIVED)
    message_user.assert_called_once_with(request, "Archived 3 project(s).")


def test_admin_site_access_is_staff_only():
    staff_request = SimpleNamespace(user=SimpleNamespace(is_active=True, is_staff=True))
    non_staff_request = SimpleNamespace(user=SimpleNamespace(is_active=True, is_staff=False))

    assert admin.site.has_permission(staff_request) is True
    assert admin.site.has_permission(non_staff_request) is False


def test_project_admin_export_action_returns_csv():
    owner = User.objects.create_user(
        username=f"project-admin-owner-{_uid()}",
        email=f"owner-{_uid()}@example.com",
    )
    project = Project.objects.create(
        title="Exportable project",
        description="Admin export test",
        owner=owner,
        status=ProjectStatus.PUBLISHED,
        source_type=ProjectSourceType.MANUAL,
        team_size=3,
        accepted_participants_count=1,
        education_program="SE",
        study_course="3",
    )
    project_admin = _project_admin()
    request = RequestFactory().get("/admin/projects/project/")

    response = project_admin.export_selected_as_csv(request, Project.objects.filter(pk=project.pk))

    content = response.content.decode("utf-8-sig")
    assert response.status_code == 200
    assert response["Content-Disposition"] == 'attachment; filename="projects-export.csv"'
    assert "id,title,status,source_type,team_size,accepted_participants_count" in content
    assert f"{project.pk},Exportable project,published,manual,3,1,SE,3," in content


def test_project_admin_export_all_view_returns_csv():
    owner = User.objects.create_user(
        username=f"project-admin-owner-all-{_uid()}",
        email=f"owner-all-{_uid()}@example.com",
    )
    project = Project.objects.create(
        title="Export all project",
        description="Admin export all test",
        owner=owner,
        status=ProjectStatus.PUBLISHED,
        source_type=ProjectSourceType.MANUAL,
    )
    project_admin = _project_admin()
    request = RequestFactory().get(reverse("admin:projects_project_export_all"))
    request.user = SimpleNamespace(is_active=True, is_staff=True)

    response = project_admin.export_all_as_csv_view(request)

    content = response.content.decode("utf-8-sig")
    assert response.status_code == 200
    assert f"{project.pk},Export all project,published,manual," in content
