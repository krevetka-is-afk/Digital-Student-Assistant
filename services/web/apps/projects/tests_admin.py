from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.projects.admin import ProjectAdmin, ProjectAdminForm
from apps.projects.models import Project, ProjectStatus
from django.contrib import admin


def _project_admin() -> ProjectAdmin:
    return admin.site._registry[Project]


def test_project_registered_in_admin():
    assert Project in admin.site._registry
    assert isinstance(_project_admin(), ProjectAdmin)


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


def test_project_admin_publish_action_updates_status():
    project_admin = _project_admin()
    project_admin.message_user = MagicMock()
    request = MagicMock()
    queryset = MagicMock()
    queryset.exclude.return_value.update.return_value = 2

    project_admin.publish_selected(request, queryset)

    queryset.exclude.assert_called_once_with(status=ProjectStatus.PUBLISHED)
    queryset.exclude.return_value.update.assert_called_once_with(status=ProjectStatus.PUBLISHED)
    project_admin.message_user.assert_called_once_with(request, "Published 2 project(s).")


def test_project_admin_archive_action_updates_status():
    project_admin = _project_admin()
    project_admin.message_user = MagicMock()
    request = MagicMock()
    queryset = MagicMock()
    queryset.exclude.return_value.update.return_value = 3

    project_admin.archive_selected(request, queryset)

    queryset.exclude.assert_called_once_with(status=ProjectStatus.ARCHIVED)
    queryset.exclude.return_value.update.assert_called_once_with(status=ProjectStatus.ARCHIVED)
    project_admin.message_user.assert_called_once_with(request, "Archived 3 project(s).")


def test_admin_site_access_is_staff_only():
    staff_request = SimpleNamespace(user=SimpleNamespace(is_active=True, is_staff=True))
    non_staff_request = SimpleNamespace(user=SimpleNamespace(is_active=True, is_staff=False))

    assert admin.site.has_permission(staff_request) is True
    assert admin.site.has_permission(non_staff_request) is False
