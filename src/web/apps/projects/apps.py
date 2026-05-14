from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    name = "apps.projects"

    def ready(self) -> None:
        from . import signals  # noqa: F401
