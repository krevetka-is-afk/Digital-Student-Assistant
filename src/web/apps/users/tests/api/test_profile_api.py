from uuid import uuid4

from apps.projects.models import Project, ProjectStatus
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def test_user_can_manage_favorite_projects():
    user = get_user_model().objects.create_user(
        username=f"fav-user-{uuid4().hex[:8]}",
        password="pass123456",
    )
    project = Project.objects.create(title="Favorite me", status=ProjectStatus.PUBLISHED)

    client = Client()
    client.force_login(user)

    add_response = client.post(
        reverse("user-profile-favorites"),
        data={"project_id": project.pk},
        content_type="application/json",
    )

    assert add_response.status_code == 200
    assert add_response.json()["project_ids"] == [project.pk]

    delete_response = client.delete(
        reverse("user-profile-favorite-detail", kwargs={"pk": project.pk}),
    )

    assert delete_response.status_code == 204
