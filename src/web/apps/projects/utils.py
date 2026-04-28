from apps.projects.models import Technology


def collect_all_tags() -> list[str]:
    """Returns a sorted list of approved technologies from the shared directory."""
    return list(
        Technology.objects.approved()
        .values_list("normalized_name", flat=True)
        .order_by("normalized_name")
    )
