from uuid import uuid4

import pytest
from apps.projects.initiative_models import InitiativeProposal
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()

pytestmark = pytest.mark.django_db


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


def _make_project(**kwargs):
    defaults = {
        "title": f"Project {_uid()}",
        "status": ProjectStatus.PUBLISHED,
        "team_size": 3,
    }
    defaults.update(kwargs)
    return Project.objects.create(**defaults)


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

    client = Client()
    response = client.get(reverse("frontend:project_list"))
    assert response.status_code == 302
    assert "/auth/" in response["Location"]


def test_toggle_bookmark_creates_and_removes():
    student = _make_student()
    project = _make_project()
    client = Client()
    client.force_login(student)

    url = reverse("frontend:toggle_bookmark", kwargs={"pk": project.pk})
    response = client.post(url, HTTP_X_CSRFTOKEN="fake", content_type="application/json")
    assert response.status_code == 200
    data = response.json()
    assert data["bookmarked"] is True
    student.profile.refresh_from_db()
    assert project.pk in student.profile.favorite_project_ids

    response = client.post(url, HTTP_X_CSRFTOKEN="fake", content_type="application/json")
    assert response.status_code == 200
    data = response.json()
    assert data["bookmarked"] is False
    student.profile.refresh_from_db()
    assert project.pk not in student.profile.favorite_project_ids


def test_project_detail_redirects_anonymous_to_auth():
    project = _make_project()
    client = Client()
    response = client.get(reverse("frontend:project_detail", kwargs={"pk": project.pk}))
    assert response.status_code == 302
    assert "/auth/" in response["Location"]


def test_project_detail_accessible_for_authenticated_student():
    student = _make_student()
    project = _make_project(status=ProjectStatus.PUBLISHED)
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:project_detail", kwargs={"pk": project.pk}))
    assert response.status_code == 200
    assert project.title in response.content.decode()


def test_project_detail_non_public_forbidden_for_non_owner():
    student = _make_student()
    project = _make_project(status=ProjectStatus.DRAFT)
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:project_detail", kwargs={"pk": project.pk}))
    assert response.status_code == 403


def test_toggle_bookmark_requires_login():
    project = _make_project()
    client = Client()
    url = reverse("frontend:toggle_bookmark", kwargs={"pk": project.pk})
    response = client.post(url)

    assert response.status_code in (302, 403)


def test_toggle_bookmark_nonexistent_project_returns_404():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.post(reverse("frontend:toggle_bookmark", kwargs={"pk": 999999}))
    assert response.status_code == 404


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

    assert response.status_code == 302

    proposal = InitiativeProposal.objects.filter(owner=student).last()
    assert proposal is not None
    assert proposal.title == "My Initiative"


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
            "supervisor_personal_data_consent": "on",
        },
    )

    proposal = InitiativeProposal.objects.filter(owner=student).last()
    assert proposal is not None
    assert proposal.supervisor_name == "Иванов Иван Иванович"


def test_initiative_project_supervisor_without_consent_rejected():
    student = _make_student()
    client = Client()
    client.force_login(student)

    response = client.post(
        reverse("frontend:initiative_project_create"),
        {
            "title": "Supervised project",
            "description": "Project with supervisor but no consent.",
            "tech_tags_raw": "",
            "team_size": "1",
            "supervisor_name": "Петров Пётр Петрович",
        },
    )
    assert response.status_code == 200
    assert not Project.objects.filter(
        owner=student, source_type=ProjectSourceType.INITIATIVE
    ).exists()


def test_initiative_project_create_redirects_anonymous():
    client = Client()
    response = client.get(reverse("frontend:initiative_project_create"))
    assert response.status_code == 302
    assert "/auth/" in response["Location"]


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


def test_recommendations_view_redirects_to_projects_tab():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:recommendations"))
    assert response.status_code == 302
    assert "tab=recs" in response["Location"]


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

    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.PUBLISHED)
    client = Client()
    client.force_login(customer)
    response = client.get(reverse("frontend:project_edit", kwargs={"pk": project.pk}))

    assert response.status_code in (302, 404)


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
    assert response.status_code == 403
    project.refresh_from_db()
    assert project.status == ProjectStatus.DRAFT


def test_project_submit_moderation_invalid_state_returns_error():
    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.PUBLISHED)
    client = Client()
    client.force_login(customer)
    response = client.post(reverse("frontend:project_submit_moderation", kwargs={"pk": project.pk}))
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.status == ProjectStatus.PUBLISHED


def test_project_delete_non_deletable_status_redirects():
    customer = _make_customer()
    project = _make_project(owner=customer, status=ProjectStatus.PUBLISHED)
    client = Client()
    client.force_login(customer)
    response = client.post(reverse("frontend:project_delete", kwargs={"pk": project.pk}))
    assert response.status_code == 302
    assert Project.objects.filter(pk=project.pk).exists()


def test_project_list_search_by_title():

    student = _make_student()
    _make_project(title="Unique Alpha Project XYZ")
    _make_project(title="Beta Project ABC")
    client = Client()
    client.force_login(student)

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


def test_customer_project_list_total_count_in_context():
    customer = _make_customer()
    _make_project(owner=customer, status=ProjectStatus.DRAFT)
    _make_project(owner=customer, status=ProjectStatus.PUBLISHED)
    client = Client()
    client.force_login(customer)
    response = client.get(reverse("frontend:project_list"))
    assert response.status_code == 200
    assert response.context["total_count"] == 2


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
    assert response.status_code == 200


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
