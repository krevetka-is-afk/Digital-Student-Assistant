from apps.projects.models import Project, ProjectStatus


def collect_all_tags() -> list[str]:
    """Returns a sorted list of all unique tech tags across published projects."""
    tags: set[str] = set()
    for tag_list in Project.objects.filter(
        status=ProjectStatus.PUBLISHED
    ).values_list("tech_tags", flat=True):
        if tag_list:
            tags.update(tag_list)
    return sorted(tags)
