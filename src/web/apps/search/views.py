from apps.projects.models import Project, ProjectStatus
from apps.projects.serializers import PrimaryProjectSerializer
from apps.recs.services import search_projects
from rest_framework import generics


class SearchListView(generics.ListAPIView):
    queryset = Project.objects.filter(status__in=ProjectStatus.catalog_values())
    serializer_class = PrimaryProjectSerializer

    def get_queryset(self, *args, **kwargs):
        q = self.request.GET.get("q")
        if not q:
            return Project.objects.none()
        _, items = search_projects(q, limit=25)
        return [item["project"] for item in items]
