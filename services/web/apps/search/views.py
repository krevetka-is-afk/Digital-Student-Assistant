from apps.projects.models import Project, ProjectStatus
from apps.projects.serializers import PrimaryProjectSerializer
from rest_framework import generics


class SearchListView(generics.ListAPIView):
    queryset = Project.objects.filter(status__in=ProjectStatus.catalog_values())
    serializer_class = PrimaryProjectSerializer

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        q = self.request.GET.get("q")
        results = Project.objects.none()
        if q is not None:
            user = None
            if self.request.user.is_authenticated:
                user = self.request.user
            results = qs.search(q, user=user)
        return results
