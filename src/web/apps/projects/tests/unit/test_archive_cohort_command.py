from __future__ import annotations

import pytest
from apps.projects.models import Project, ProjectStatus
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


def _make_project(title: str, year: str, status: str) -> Project:
    return Project.objects.create(title=title, academic_year=year, status=status)


# ---------------------------------------------------------------------------
# No matching projects
# ---------------------------------------------------------------------------

def test_archive_cohort_no_projects_found(capsys):
    call_command("archive_cohort", "2020-2021")
    out = capsys.readouterr().out
    assert "No archivable projects found" in out


# ---------------------------------------------------------------------------
# Archiving by status
# ---------------------------------------------------------------------------

def test_archive_cohort_archives_published_projects():
    p = _make_project("Project A", "2024-2025", ProjectStatus.PUBLISHED)
    call_command("archive_cohort", "2024-2025")
    p.refresh_from_db()
    assert p.status == ProjectStatus.ARCHIVED


def test_archive_cohort_archives_staffed_projects():
    p = _make_project("Project B", "2024-2025", ProjectStatus.STAFFED)
    call_command("archive_cohort", "2024-2025")
    p.refresh_from_db()
    assert p.status == ProjectStatus.ARCHIVED


def test_archive_cohort_archives_completed_projects():
    p = _make_project("Project C", "2024-2025", ProjectStatus.COMPLETED)
    call_command("archive_cohort", "2024-2025")
    p.refresh_from_db()
    assert p.status == ProjectStatus.ARCHIVED


# ---------------------------------------------------------------------------
# Non-archivable statuses must not be touched
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", [
    ProjectStatus.DRAFT,
    ProjectStatus.ON_MODERATION,
    ProjectStatus.CANCELLED,
    ProjectStatus.REJECTED,
    ProjectStatus.ARCHIVED,
])
def test_archive_cohort_skips_non_archivable_statuses(status):
    p = _make_project(f"Project {status}", "2024-2025", status)
    call_command("archive_cohort", "2024-2025")
    p.refresh_from_db()
    assert p.status == status


# ---------------------------------------------------------------------------
# Only the requested academic year is affected
# ---------------------------------------------------------------------------

def test_archive_cohort_does_not_touch_other_years():
    target = _make_project("Target year", "2024-2025", ProjectStatus.PUBLISHED)
    other = _make_project("Other year", "2023-2024", ProjectStatus.PUBLISHED)

    call_command("archive_cohort", "2024-2025")

    target.refresh_from_db()
    other.refresh_from_db()
    assert target.status == ProjectStatus.ARCHIVED
    assert other.status == ProjectStatus.PUBLISHED


# ---------------------------------------------------------------------------
# Dry-run: no changes committed
# ---------------------------------------------------------------------------

def test_archive_cohort_dry_run_does_not_change_status(capsys):
    p = _make_project("Dry-run project", "2024-2025", ProjectStatus.PUBLISHED)

    call_command("archive_cohort", "2024-2025", dry_run=True)

    p.refresh_from_db()
    assert p.status == ProjectStatus.PUBLISHED
    out = capsys.readouterr().out
    assert "Dry run" in out


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

def test_archive_cohort_empty_year_raises():
    with pytest.raises((CommandError, SystemExit)):
        call_command("archive_cohort", "")
