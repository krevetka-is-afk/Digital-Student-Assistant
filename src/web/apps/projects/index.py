from algoliasearch_django import AlgoliaIndex
from algoliasearch_django.decorators import register

from .models import Project


@register(Project)
class ProjectIndex(AlgoliaIndex):
    should_index = "is_public"
    fields = [
        "title",
        "description",
        "status",
        "tech_tags",
    ]
    tags = "get_tags_list"


# admin.site.register(Project, ProjectModelAdmin)
