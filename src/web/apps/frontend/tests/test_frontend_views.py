"""
Frontend view tests: bookmarks, initiative project, profile, tab redirects.
"""
from uuid import uuid4

from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()


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

    project = Project.objects.filter(
        owner=student, source_type=ProjectSourceType.INITIATIVE
    ).last()
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
    _make_project(
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
    # Should raise 404 (role guard) or redirect
    assert response.status_code in (302, 404)


def test_moderation_list_accessible_for_cpprp():
    cpprp = _make_cpprp()
    client = Client()
    client.force_login(cpprp)
    response = client.get(reverse("frontend:moderation_list"))
    assert response.status_code == 200
    assert "Очередь модерации" in response.content.decode()
