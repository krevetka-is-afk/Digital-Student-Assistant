from apps.projects.models import ProjectStatus
from rest_framework import generics, permissions

from .models import FacultyMatchStatus, FacultyPerson, ProjectFacultyMatch
from .serializers import FacultyPersonSerializer, ProjectFacultyMatchPublicSerializer


class FacultyPersonListAPIView(generics.ListAPIView):
    serializer_class = FacultyPersonSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = FacultyPerson.objects.filter(is_stale=False).order_by("full_name")
        query = (self.request.query_params.get("q") or "").strip()
        interest = (self.request.query_params.get("interest") or "").strip().lower()
        if query:
            queryset = queryset.filter(full_name__icontains=query)
        if interest:
            queryset = [
                person
                for person in queryset
                if interest in {str(item).strip().lower() for item in (person.interests or [])}
            ]
        return queryset


class FacultyPersonDetailAPIView(generics.RetrieveAPIView):
    serializer_class = FacultyPersonSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = "source_key"
    lookup_url_kwarg = "source_key"

    def get_queryset(self):
        return FacultyPerson.objects.filter(is_stale=False)


class FacultyPersonProjectsAPIView(generics.ListAPIView):
    serializer_class = ProjectFacultyMatchPublicSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return (
            ProjectFacultyMatch.objects.select_related("project", "faculty_person")
            .filter(
                faculty_person__source_key=self.kwargs["source_key"],
                status=FacultyMatchStatus.CONFIRMED,
                project__status__in=ProjectStatus.catalog_values(),
            )
            .order_by("project_id")
        )
