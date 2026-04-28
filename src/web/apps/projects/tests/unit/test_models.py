from uuid import uuid4

from apps.projects.models import (
    Project,
    ProjectSourceType,
    ProjectStatus,
    Technology,
    TechnologyStatus,
)


def test_project_defaults():
    project = Project(title="Data platform")

    assert project.status == ProjectStatus.DRAFT
    assert project.source_type == ProjectSourceType.MANUAL
    assert project.tech_tags == []


def test_technology_normalizes_name_on_save():
    suffix = uuid4().hex[:8]
    technology = Technology.objects.create(name=f" Test Tech {suffix} ")

    assert technology.name == f"test tech {suffix}"
    assert technology.normalized_name == f"test tech {suffix}"
    assert technology.status == TechnologyStatus.PENDING


def test_project_save_links_normalized_technology_directory_entries():
    project = Project.objects.create(
        title="Directory sync",
        tech_tags=[" Python ", "python", "React  Native"],
    )

    assert project.tech_tags == ["python", "react native"]
    assert list(
        project.technologies.order_by("normalized_name").values_list("normalized_name", flat=True)
    ) == [
        "python",
        "react native",
    ]
    assert Technology.objects.filter(normalized_name="python").exists()
