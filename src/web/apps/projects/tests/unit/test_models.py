from apps.projects.models import Project, ProjectSourceType, ProjectStatus


def test_project_defaults():
    project = Project(title="Data platform")

    assert project.status == ProjectStatus.DRAFT
    assert project.source_type == ProjectSourceType.MANUAL
    assert project.tech_tags == []
