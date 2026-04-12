from uuid import uuid4

from apps.applications.models import Application
from apps.projects.models import Project, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def _user_with_role(*, username: str, email: str, role: str):
    suffix = uuid4().hex[:8]
    user = get_user_model().objects.create_user(
        username=f"{username}_{suffix}",
        email=f"{suffix}.{email}",
        password="password123",
    )
    UserProfile.objects.create(user=user, role=role)
    return user


def test_auth_login_ignores_external_next_redirect():
    user = _user_with_role(username="student1", email="student1@example.com", role=UserRole.STUDENT)
    client = Client()

    response = client.post(
        f"{reverse('frontend:auth')}?next=https://evil.example/phish",
        data={
            "tab": "login",
            "email": user.email,
            "password": "password123",
            "next": "https://evil.example/phish",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("frontend:project_list")


def test_quick_apply_rejects_non_student_roles():
    owner = _user_with_role(username="owner1", email="owner1@example.com", role=UserRole.CUSTOMER)
    applicant = _user_with_role(
        username="customer1", email="customer1@example.com", role=UserRole.CUSTOMER
    )
    project = Project.objects.create(
        title="AI Project",
        owner=owner,
        status=ProjectStatus.PUBLISHED,
        team_size=2,
    )

    client = Client()
    assert client.login(username=applicant.username, password="password123")
    response = client.post(reverse("frontend:apply_to_project", kwargs={"pk": project.pk}))

    assert response.status_code == 400
    assert Application.objects.filter(project=project, applicant=applicant).count() == 0


def test_quick_apply_rejects_non_open_project():
    owner = _user_with_role(username="owner2", email="owner2@example.com", role=UserRole.CUSTOMER)
    applicant = _user_with_role(
        username="student2",
        email="student2@example.com",
        role=UserRole.STUDENT,
    )
    project = Project.objects.create(
        title="Closed Project",
        owner=owner,
        status=ProjectStatus.STAFFED,
        team_size=1,
        accepted_participants_count=1,
    )

    client = Client()
    assert client.login(username=applicant.username, password="password123")
    response = client.post(reverse("frontend:apply_to_project", kwargs={"pk": project.pk}))

    assert response.status_code == 400
    assert Application.objects.filter(project=project, applicant=applicant).count() == 0
