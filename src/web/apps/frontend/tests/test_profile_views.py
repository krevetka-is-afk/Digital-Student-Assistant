from uuid import uuid4

import pytest
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()

pytestmark = pytest.mark.django_db


def _uid():
    return uuid4().hex[:8]


def _make_student(interests=None):
    user = User.objects.create_user(username=f"stu-{_uid()}", password="pass")
    UserProfile.objects.create(user=user, role=UserRole.STUDENT, interests=interests or [])
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
    defaults = {"title": f"Project {_uid()}", "status": ProjectStatus.PUBLISHED, "team_size": 3}
    defaults.update(kwargs)
    return Project.objects.create(**defaults)


def test_profile_unauth_redirects_to_login():
    response = Client().get(reverse("frontend:profile"))
    assert response.status_code == 302
    assert "/auth/" in response["Location"]


def test_profile_get_renders_for_student():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:profile"))
    assert response.status_code == 200


def test_profile_get_renders_for_customer():
    customer = _make_customer()
    client = Client()
    client.force_login(customer)
    response = client.get(reverse("frontend:profile"))
    assert response.status_code == 200


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
    assert response.status_code == 302

    student.refresh_from_db()
    assert student.first_name == "Иван"
    assert student.last_name == "Петров"

    student.profile.refresh_from_db()
    assert student.profile.bio == "Студент МИЭМ"
    assert "python" in student.profile.interests


def test_profile_update_double_space_name():
    student = _make_student()
    client = Client()
    client.force_login(student)

    client.post(
        reverse("frontend:profile"),
        {
            "full_name": "Иван  Петров",
            "bio": "Студент МИЭМ",
            "interests_raw": "",
        },
    )
    student.refresh_from_db()
    assert student.last_name == "Петров"


def test_profile_update_single_word_name_clears_last_name():
    student = _make_student()
    student.last_name = "Старая"
    student.save(update_fields=["last_name"])
    client = Client()
    client.force_login(student)

    client.post(
        reverse("frontend:profile"),
        {"full_name": "Иван", "bio": "", "interests_raw": ""},
    )
    student.refresh_from_db()
    assert student.first_name == "Иван"
    assert student.last_name == ""


def test_profile_update_short_bio_rejected():
    student = _make_student()
    client = Client()
    client.force_login(student)

    response = client.post(
        reverse("frontend:profile"),
        {"full_name": "Иван Петров", "bio": "Коротко", "interests_raw": ""},
    )
    assert response.status_code == 200
    assert response.context["form"].errors


def test_profile_get_renders_for_cpprp():
    cpprp = _make_cpprp()
    client = Client()
    client.force_login(cpprp)
    response = client.get(reverse("frontend:profile"))
    assert response.status_code == 200
    assert response.context["moderation_queue_count"] == 0
