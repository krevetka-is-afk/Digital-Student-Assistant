from rest_framework import mixins, viewsets

from .models import Project
from .serializers import PrimaryProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    """
    Docstring for ProjectViewSet
    get -> list -> Queryset
    get -> retrive -> Project instance detail view
    post -> create -> new instance
    put -> update
    patch -> partial update
    delete -> destroy
    """

    queryset = Project.objects.all()
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"  # default


class ProjectGenericViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    Docstring for ProjectGenericViewSet
    get -> list -> Queryset
    get -> retrive -> Project instance detail view
    """

    queryset = Project.objects.all()
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"  # default


project_list_view = ProjectGenericViewSet.as_view({"get": "list"})
project_detail_view = ProjectGenericViewSet.as_view({"get": "retrive"})
