"""
Frontend view tests: bookmarks, initiative project, profile, tab redirects,
project CRUD, filtering, application review, moderation workflow.
"""

from datetime import timedelta
from uuid import uuid4

import pytest
from apps.applications.models import Application, ApplicationStatus
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

User = get_user_model()

# All tests in this module require database access; pytest-django wraps each
# test in a transaction that is rolled back after the test, providing full
# isolation without accumulating stale data across test runs.
pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid():
    return uuid4().hex[:8]


def _make_student(interests=None):
    user = User.objects.create_user(username=f"stu-{_uid()}", password="pass")
    UserProfile.objects.create(
        user=user,
        role=UserRole.STUDENT,
        interests=interests or [],
    )
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
    defaults = {
        "title": f"Project {_uid()}",
        "status": ProjectStatus.PUBLISHED,
        "team_size": 3,
    }
    defaults.update(kwargs)
    return Project.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Project list — tabs visible for students
# ---------------------------------------------------------------------------


def test_project_list_shows_tabs_for_student():
    client = Client()
    client.force_login(_make_student())
    response = client.get(reverse("frontend:project_list"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "tab-btn-recs" in content
    assert "tab-btn-bookmarks" in content
    assert "tab-btn-applications" in content


def test_project_list_redirects_anonymous_to_auth():
    """Unauthenticated users must be redirected to login — the platform is not public."""
    client = Client()
    response = client.get(reverse("frontend:project_list"))
    assert response.status_code == 302
    assert "/auth/" in response["Location"]


# ---------------------------------------------------------------------------
# Bookmark toggle
# ---------------------------------------------------------------------------


def test_toggle_bookmark_creates_and_removes():
    student = _make_student()
    project = _make_project()
    client = Client()
    client.force_login(student)

    # First toggle — should add to favorites
    url = reverse("frontend:toggle_bookmark", kwargs={"pk": project.pk})
    response = client.post(url, HTTP_X_CSRFTOKEN="fake", content_type="application/json")
    assert response.status_code == 200
    data = response.json()
    assert data["bookmarked"] is True
    student.profile.refresh_from_db()
    assert project.pk in student.profile.favorite_project_ids

    # Second toggle — should remove from favorites
    response = client.post(url, HTTP_X_CSRFTOKEN="fake", content_type="application/json")
    assert response.status_code == 200
    data = response.json()
    assert data["bookmarked"] is False
    student.profile.refresh_from_db()
    assert project.pk not in student.profile.favorite_project_ids


def test_project_detail_redirects_anonymous_to_auth():
    """Direct link to a project detail must require login."""
    project = _make_project()
    client = Client()
    response = client.get(reverse("frontend:project_detail", kwargs={"pk": project.pk}))
    assert response.status_code == 302
    assert "/auth/" in response["Location"]


def test_submit_application_returns_401_json_for_anonymous():
    """fetch() submit from modal must get JSON 401, not HTML redirect."""
    project = _make_project()
    client = Client()
    url = reverse("frontend:submit_application", kwargs={"pk": project.pk})
    response = client.post(url, {"motivation": "test", "source": "card"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "unauthenticated"
    assert "redirect" in data


def test_toggle_bookmark_requires_login():
    project = _make_project()
    client = Client()
    url = reverse("frontend:toggle_bookmark", kwargs={"pk": project.pk})
    response = client.post(url)
    # Should redirect to auth page
    assert response.status_code in (302, 403)


def test_bookmarked_project_appears_in_bookmarks_tab():
    student = _make_student()
    project = _make_project()
    student.profile.set_favorite_project_ids([project.pk])
    student.profile.save(update_fields=["favorite_project_ids"])
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:project_list"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "tab-panel-bookmarks" in content
    assert project.title in content


# ---------------------------------------------------------------------------
# Initiative project creation
# ---------------------------------------------------------------------------


def test_initiative_form_get_renders_for_student():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:initiative_project_create"))
    assert response.status_code == 200
    assert "Инициативный проект" in response.content.decode()


def test_initiative_form_get_redirects_for_customer():
    customer = _make_customer()
    client = Client()
    client.force_login(customer)
    response = client.get(reverse("frontend:initiative_project_create"))
    # Customer is not a student — should be redirected
    assert response.status_code == 302


def test_initiative_project_create_post_valid():
    student = _make_student()
    client = Client()
    client.force_login(student)

    response = client.post(
        reverse("frontend:initiative_project_create"),
        {
            "title": "My Initiative",
            "description": "A detailed description of my project idea.",
            "tech_tags_raw": "Python, FastAPI",
            "team_size": "2",
            "supervisor_name": "",
        },
    )
    # Should redirect to project detail on success
    assert response.status_code == 302

    project = Project.objects.filter(
        owner=student,
        source_type=ProjectSourceType.INITIATIVE,
    ).last()
    assert project is not None
    assert project.title == "My Initiative"
    assert project.status == ProjectStatus.ON_MODERATION
    assert "python" in project.tech_tags
    assert "fastapi" in project.tech_tags


def test_initiative_project_create_post_invalid_no_title():
    student = _make_student()
    client = Client()
    client.force_login(student)

    response = client.post(
        reverse("frontend:initiative_project_create"),
        {
            "title": "",
            "description": "Has description but no title.",
            "tech_tags_raw": "",
            "team_size": "1",
        },
    )
    # Should re-render form with errors
    assert response.status_code == 200
    assert "Название обязательно" in response.content.decode()


def test_initiative_project_with_supervisor():
    student = _make_student()
    client = Client()
    client.force_login(student)

    client.post(
        reverse("frontend:initiative_project_create"),
        {
            "title": "Supervised project",
            "description": "Project with a supervisor name set.",
            "tech_tags_raw": "",
            "team_size": "1",
            "supervisor_name": "Иванов Иван Иванович",
        },
    )

    project = Project.objects.filter(owner=student, source_type=ProjectSourceType.INITIATIVE).last()
    assert project is not None
    assert project.supervisor_name == "Иванов Иван Иванович"


# ---------------------------------------------------------------------------
# Initiative projects appear in Applications tab for their owner
# ---------------------------------------------------------------------------


def test_initiative_projects_visible_in_applications_tab():
    student = _make_student()
    project = _make_project(
        owner=student,
        source_type=ProjectSourceType.INITIATIVE,
        status=ProjectStatus.ON_MODERATION,
    )
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:project_list"))
    assert response.status_code == 200
    assert project.title in response.content.decode()


# ---------------------------------------------------------------------------
# Profile view
# ---------------------------------------------------------------------------


def test_profile_view_shows_student_stats():
    student = _make_student()
    _project = _make_project(
        owner=student,
        source_type=ProjectSourceType.INITIATIVE,
        status=ProjectStatus.ON_MODERATION,
    )
    bm_project = _make_project()
    student.profile.set_favorite_project_ids([bm_project.pk])
    student.profile.save(update_fields=["favorite_project_ids"])
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:profile"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Заявок подано" in content or "Заявка подана" in content or "Заявки подано" in content
    assert "Закладка" in content or "Закладок" in content or "Закладки" in content
    assert "Инициативный проект" in content or "Инициативных проекта" in content


def test_profile_update_post_saves_name():
    student = _make_student()
    client = Client()
    client.force_login(student)

    response = client.post(
        reverse("frontend:profile"),
        {
            "full_name": "Иван Петров",
            "bio": "Студент МИЭМ",
            "interests_raw": "Python,Django",
        },
    )
    # Should redirect after save
    assert response.status_code == 302

    student.refresh_from_db()
    assert student.first_name == "Иван"
    assert student.last_name == "Петров"

    student.profile.refresh_from_db()
    assert student.profile.bio == "Студент МИЭМ"
    assert "Python" in student.profile.interests


# ---------------------------------------------------------------------------
# Legacy redirects
# ---------------------------------------------------------------------------


def test_application_list_redirects_to_projects_tab():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:application_list"))
    assert response.status_code == 302
    assert "tab=applications" in response["Location"]


def test_recommendations_view_redirects_to_projects_tab():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:recommendations"))
    assert response.status_code == 302
    assert "tab=recs" in response["Location"]


# ---------------------------------------------------------------------------
# Moderation: only CPPRP can access
# ---------------------------------------------------------------------------


def test_moderation_list_forbidden_for_student():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:moderation_list"))
    # Should be 403 (PermissionDenied from @moderator_required), 404, or redirect
    assert response.status_code in (302, 403, 404)


def test_moderation_list_accessible_for_cpprp():
    cpprp = _make_cpprp()
    client = Client()
    client.force_login(cpprp)
    response = client.get(reverse("frontend:moderation_list"))
    assert response.status_code == 200
    assert "Очередь модерации" in response.content.decode()


# ---------------------------------------------------------------------------
# Project create (customer only)
# ---------------------------------------------------------------------------


def test_project_create_get_renders_for_customer():
    customer = _make_customer()
    client = Client()
    client.force_login(customer)
    response = client.get(reverse("frontend:project_create"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "form" in content.lower()


def test_project_create_redirects_student():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:project_create"))
    assert response.status_code == 302


def test_project_create_post_valid():
    customer = _make_customer()
    client = Client()
    client.force_login(customer)
    response = client.post(
        reverse("frontend:project_create"),
        {
            "title": "New Test Project",
            "description": "A sufficiently long description for the project.",
            "tech_tags_raw": "Python, Django",
            "team_size": "3",
        },
    )
    assert response.status_code == 302
    project = Project.objects.filter(owner=customer, title="New Test Project").last()
    assert project is not None
    assert project.status == ProjectStatus.DRAFT
    assert "python" in project.tech_tags
    assert "django" in project.tech_tags


def test_project_create_post_invalid_no_title():
    customer = _make_customer()
    client = Client()
    client.force_login(customer)
    response = client.post(
        reverse("frontend:project_create"),
        {"title": "", "description": "desc", "tech_tags_raw": "", "team_size": "3"},
    )
    assert response.status_code == 200
    assert "Название обязательно" in response.content.decode()


def test_project_create_post_invalid_team_size_zero():
    customer = _make_customer()
    client = Client()
    client.force_login(customer)
    response = client.post(
        reverse("frontend:project_create"),
        {"title": "Title", "description": "desc", "tech_tags_raw": "", "team_size": "0"},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Project edit (owner only)
# ---------------------------------------------------------------------------


def test_project_edit_get_renders_for_owner():
    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.DRAFT)
    client = Client()
    client.force_login(customer)
    response = client.get(reverse("frontend:project_edit", kwargs={"pk": project.pk}))
    assert response.status_code == 200
    assert project.title in response.content.decode()


def test_project_edit_forbidden_for_non_owner():
    owner = _make_customer()
    other = _make_customer()
    project = _make_project(owner=owner, status=ProjectStatus.DRAFT)
    client = Client()
    client.force_login(other)
    response = client.get(reverse("frontend:project_edit", kwargs={"pk": project.pk}))
    assert response.status_code in (403, 404)


def test_project_edit_post_updates_project():
    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.DRAFT)
    client = Client()
    client.force_login(customer)
    response = client.post(
        reverse("frontend:project_edit", kwargs={"pk": project.pk}),
        {
            "title": "Updated Title",
            "description": "Updated description text.",
            "tech_tags_raw": "Go, Kubernetes",
            "team_size": "5",
        },
    )
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.title == "Updated Title"
    assert project.team_size == 5
    assert "go" in project.tech_tags


def test_project_edit_locked_for_published_project():
    """Published projects cannot be edited — form should reject or redirect."""
    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.PUBLISHED)
    client = Client()
    client.force_login(customer)
    response = client.get(reverse("frontend:project_edit", kwargs={"pk": project.pk}))
    # Either redirect or 404 — published projects are locked
    assert response.status_code in (302, 404)


# ---------------------------------------------------------------------------
# Project delete
# ---------------------------------------------------------------------------


def test_project_delete_by_owner():
    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.DRAFT)
    pk = project.pk
    client = Client()
    client.force_login(customer)
    response = client.post(reverse("frontend:project_delete", kwargs={"pk": pk}))
    assert response.status_code == 302
    assert not Project.objects.filter(pk=pk).exists()


def test_project_delete_forbidden_for_non_owner():
    owner = _make_customer()
    other = _make_customer()
    project = _make_project(owner=owner, status=ProjectStatus.DRAFT)
    client = Client()
    client.force_login(other)
    response = client.post(reverse("frontend:project_delete", kwargs={"pk": project.pk}))
    assert response.status_code in (403, 404)
    assert Project.objects.filter(pk=project.pk).exists()


# ---------------------------------------------------------------------------
# Project submit for moderation
# ---------------------------------------------------------------------------


def test_project_submit_moderation_by_owner():
    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.DRAFT)
    client = Client()
    client.force_login(customer)
    response = client.post(reverse("frontend:project_submit_moderation", kwargs={"pk": project.pk}))
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.status == ProjectStatus.ON_MODERATION


def test_project_submit_moderation_forbidden_for_non_owner():
    owner = _make_customer()
    other = _make_customer()
    project = _make_project(owner=owner, status=ProjectStatus.DRAFT)
    client = Client()
    client.force_login(other)
    response = client.post(reverse("frontend:project_submit_moderation", kwargs={"pk": project.pk}))
    assert response.status_code in (302, 403, 404)
    project.refresh_from_db()
    assert project.status == ProjectStatus.DRAFT


# ---------------------------------------------------------------------------
# Filtering: search and tag filter
# ---------------------------------------------------------------------------


def test_project_list_search_by_title():
    """Search filter returns matching projects via HTMX partial response."""
    student = _make_student()
    _make_project(title="Unique Alpha Project XYZ")
    _make_project(title="Beta Project ABC")
    client = Client()
    client.force_login(student)
    # Use HTMX headers to get only the filtered projects-section partial
    response = client.get(
        reverse("frontend:project_list"),
        {"q": "Alpha"},
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="projects-section",
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Unique Alpha Project XYZ" in content
    assert "Beta Project ABC" not in content


@pytest.mark.skipif(
    "sqlite3" in settings.DATABASES["default"]["ENGINE"],
    reason="JSON containment filter requires PostgreSQL",
)
def test_project_list_filter_by_tag():
    """Tag filter uses PostgreSQL JSON containment — skipped on SQLite."""
    student = _make_student()
    _make_project(title="Tagged Project", tech_tags=["fastapi", "python"])
    _make_project(title="Untagged Project", tech_tags=[])
    client = Client()
    client.force_login(student)
    response = client.get(
        reverse("frontend:project_list"),
        {"tech_tags": "fastapi"},
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="projects-section",
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Tagged Project" in content
    assert "Untagged Project" not in content


def test_project_list_search_no_results():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:project_list"), {"q": "zzz_nonexistent_query_xyz"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Customer project list
# ---------------------------------------------------------------------------


def test_customer_sees_own_projects():
    customer = _make_customer()
    own = _make_project(owner=customer, status=ProjectStatus.DRAFT)
    other_customer = _make_customer()
    other = _make_project(owner=other_customer, status=ProjectStatus.PUBLISHED)
    client = Client()
    client.force_login(customer)
    response = client.get(reverse("frontend:project_list"))
    assert response.status_code == 200
    content = response.content.decode()
    assert own.title in content
    assert other.title not in content


# ---------------------------------------------------------------------------
# Application review (accept / reject)
# ---------------------------------------------------------------------------


def test_project_applications_accessible_by_owner():
    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.PUBLISHED)
    client = Client()
    client.force_login(customer)
    response = client.get(reverse("frontend:project_applications", kwargs={"pk": project.pk}))
    assert response.status_code == 200


def test_project_applications_forbidden_for_non_owner():
    owner = _make_customer()
    other = _make_customer()
    project = _make_project(owner=owner, status=ProjectStatus.PUBLISHED)
    client = Client()
    client.force_login(other)
    response = client.get(reverse("frontend:project_applications", kwargs={"pk": project.pk}))
    assert response.status_code in (302, 403, 404)


def test_review_application_accept():
    customer = _make_customer()
    student = _make_student()
    project = _make_project(owner=customer, status=ProjectStatus.PUBLISHED, team_size=3)
    application = Application.objects.create(
        project=project, applicant=student, status=ApplicationStatus.SUBMITTED
    )
    client = Client()
    client.force_login(customer)
    response = client.post(
        reverse("frontend:review_application", kwargs={"pk": application.pk}),
        {"decision": "accept", "comment": ""},
    )
    assert response.status_code == 302
    application.refresh_from_db()
    assert application.status == ApplicationStatus.ACCEPTED


def test_review_application_reject_requires_comment():
    customer = _make_customer()
    student = _make_student()
    project = _make_project(owner=customer, status=ProjectStatus.PUBLISHED)
    application = Application.objects.create(
        project=project, applicant=student, status=ApplicationStatus.SUBMITTED
    )
    client = Client()
    client.force_login(customer)
    # Reject without comment — should fail
    client.post(
        reverse("frontend:review_application", kwargs={"pk": application.pk}),
        {"decision": "reject", "comment": ""},
    )
    # Either re-renders with error or redirects (depends on implementation)
    application.refresh_from_db()
    assert application.status == ApplicationStatus.SUBMITTED  # not changed


def test_review_application_reject_with_comment():
    customer = _make_customer()
    student = _make_student()
    project = _make_project(owner=customer, status=ProjectStatus.PUBLISHED)
    application = Application.objects.create(
        project=project, applicant=student, status=ApplicationStatus.SUBMITTED
    )
    client = Client()
    client.force_login(customer)
    response = client.post(
        reverse("frontend:review_application", kwargs={"pk": application.pk}),
        {
            "decision": "reject",
            "comment": "К сожалению, ваша заявка не соответствует требованиям проекта.",
        },
    )
    assert response.status_code == 302
    application.refresh_from_db()
    assert application.status == ApplicationStatus.REJECTED


def test_review_application_forbidden_for_non_owner():
    owner = _make_customer()
    other = _make_customer()
    student = _make_student()
    project = _make_project(owner=owner, status=ProjectStatus.PUBLISHED)
    application = Application.objects.create(
        project=project, applicant=student, status=ApplicationStatus.SUBMITTED
    )
    client = Client()
    client.force_login(other)
    response = client.post(
        reverse("frontend:review_application", kwargs={"pk": application.pk}),
        {"decision": "accept", "comment": ""},
    )
    assert response.status_code in (302, 403, 404)
    application.refresh_from_db()
    assert application.status == ApplicationStatus.SUBMITTED


# ---------------------------------------------------------------------------
# Moderation workflow (approve / reject)
# ---------------------------------------------------------------------------


def test_moderation_decide_approve():
    cpprp = _make_cpprp()
    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.ON_MODERATION)
    client = Client()
    client.force_login(cpprp)
    response = client.post(
        reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
        {"decision": "approve", "comment": ""},
    )
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.status == ProjectStatus.PUBLISHED


def test_moderation_decide_reject_with_comment():
    cpprp = _make_cpprp()
    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.ON_MODERATION)
    client = Client()
    client.force_login(cpprp)
    response = client.post(
        reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
        {
            "decision": "reject",
            "comment": (  # noqa: E501 — long Cyrillic string is intentional test fixture
                "Проект не соответствует требованиям программы. Необходимо доработать описание, "
                "добавить конкретные результаты, критерии отбора и ожидаемый формат работы."
            ),
        },
    )
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.status == ProjectStatus.REJECTED


def test_moderation_decide_forbidden_for_student():
    student = _make_student()
    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.ON_MODERATION)
    client = Client()
    client.force_login(student)
    response = client.post(
        reverse("frontend:moderate_project_decide", kwargs={"pk": project.pk}),
        {"decision": "approve", "comment": ""},
    )
    assert response.status_code in (302, 403, 404)
    project.refresh_from_db()
    assert project.status == ProjectStatus.ON_MODERATION


def test_moderation_queue_shows_pending_projects():
    """Moderation queue shows ON_MODERATION projects; DRAFT projects are not shown."""
    cpprp = _make_cpprp()
    customer = _make_customer()
    pending_title = f"Pending {_uid()}"
    draft_title = f"Draft {_uid()}"
    pending_project = _make_project(
        owner=customer, status=ProjectStatus.ON_MODERATION, title=pending_title
    )
    _make_project(owner=customer, status=ProjectStatus.DRAFT, title=draft_title)
    Project.objects.filter(pk=pending_project.pk).update(
        updated_at=timezone.now() - timedelta(days=3650)
    )
    client = Client()
    client.force_login(cpprp)
    response = client.get(reverse("frontend:moderation_list"))
    assert response.status_code == 200
    content = response.content.decode()
    # Pending project must be in the queue
    assert pending_title in content
    # Draft project must NOT appear in the moderation queue
    assert draft_title not in content


# ---------------------------------------------------------------------------
# Tag validation edge cases
# ---------------------------------------------------------------------------


def test_initiative_project_invalid_tag_rejected():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.post(
        reverse("frontend:initiative_project_create"),
        {
            "title": "Valid title",
            "description": "Valid description.",
            "tech_tags_raw": "!!!invalid_tag!!!",
            "team_size": "1",
        },
    )
    assert response.status_code == 200  # Re-renders form with error


def test_project_create_duplicate_tags_deduplicated():
    customer = _make_customer()
    client = Client()
    client.force_login(customer)
    client.post(
        reverse("frontend:project_create"),
        {
            "title": "Dedup Test",
            "description": "Testing tag deduplication.",
            "tech_tags_raw": "Python, python, PYTHON",
            "team_size": "2",
        },
    )
    project = Project.objects.filter(owner=customer, title="Dedup Test").last()
    if project:
        assert project.tech_tags.count("python") == 1


# ---------------------------------------------------------------------------
# Auth: registration validation
# ---------------------------------------------------------------------------


def test_register_rejects_invalid_email():
    """'sdfsdf' is not a valid email — registration must be refused."""
    client = Client()
    response = client.post(
        reverse("frontend:auth"),
        {"tab": "register", "email": "sdfsdf", "password": "ValidPass1", "role": "student"},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "корректный email" in content
    # No user should have been created with that garbage email
    assert not User.objects.filter(email="sdfsdf").exists()


def test_register_rejects_email_missing_domain():
    client = Client()
    response = client.post(
        reverse("frontend:auth"),
        {"tab": "register", "email": "user@", "password": "ValidPass1", "role": "student"},
    )
    assert response.status_code == 200
    assert "корректный email" in response.content.decode()


def test_register_accepts_valid_email():
    uid = _uid()
    client = Client()
    response = client.post(
        reverse("frontend:auth"),
        {
            "tab": "register",
            "email": f"valid_{uid}@example.com",
            "password": "ValidPass1",
            "role": "student",
        },
    )
    assert response.status_code == 302
    assert User.objects.filter(email=f"valid_{uid}@example.com").exists()


def test_register_rejects_short_password():
    uid = _uid()
    client = Client()
    response = client.post(
        reverse("frontend:auth"),
        {
            "tab": "register",
            "email": f"u_{uid}@example.com",
            "password": "short",
            "role": "student",
        },
    )
    assert response.status_code == 200
    assert "не менее 8" in response.content.decode()


def test_register_rejects_duplicate_email():
    uid = _uid()
    email = f"dup_{uid}@example.com"
    User.objects.create_user(username=f"existing_{uid}", email=email, password="somepass1")
    client = Client()
    response = client.post(
        reverse("frontend:auth"),
        {"tab": "register", "email": email, "password": "ValidPass1", "role": "student"},
    )
    assert response.status_code == 200
    assert "уже существует" in response.content.decode()


def test_login_rejects_invalid_email_format():
    client = Client()
    response = client.post(
        reverse("frontend:auth"),
        {"tab": "login", "email": "notanemail", "password": "anything"},
    )
    assert response.status_code == 200
    assert "корректный email" in response.content.decode()
