# from django.http import Http404
from apps.base.mixins import StaffEditorPermissionMixin, UserQuerySetMixin
from apps.base.permissions import IsStaffEditorPermission
from django.shortcuts import get_object_or_404
from rest_framework import generics, mixins
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Project
from .serializers import PrimaryProjectSerializer


class ProjectListCreateAPIView(
    generics.ListCreateAPIView, UserQuerySetMixin, StaffEditorPermissionMixin
):
    """
    Docstring for ProjectListCreateAPIView

    GET for List
    POST for creation
    """

    queryset = Project.objects.all()
    serializer_class = PrimaryProjectSerializer

    def perform_create(self, serializer):
        # serializer.save(user=self.request.user)
        # print(serializer.validated_data)
        # email = serializer.validated_data.pop("email")
        # print(email)
        title = serializer.validated_data.get("title")
        content = serializer.validated_data.get("content")

        if content is None:
            content = title

        serializer.save(user=self.request.user, content=content)  # form.save() model.save()
        # send django signal

        # return super().perform_create(serializer)

    # def get_queryset(self, *args, **kwargs):
    #     qs = super().get_queryset(*args, **kwargs)
    #     request = self.request
    #     user = request.user
    #     # print(request.user)
    #     if not user.is_authenticated:
    #         return Project.objects.none()

    #     return qs.filter(user=request.user)


project_list_create_view = ProjectListCreateAPIView.as_view()


class ProjectDetailAPIView(StaffEditorPermissionMixin, UserQuerySetMixin, generics.RetrieveAPIView):
    """
    Docstring for ProjectDetailAPIView

    GET for lookup_field
    """

    queryset = Project.objects.all()
    serializer_class = PrimaryProjectSerializer
    # lookup_field = 'pk'
    # Project.objects.get(pk)


project_detail_view = ProjectDetailAPIView.as_view()


class ProjectUpdateAPIView(IsStaffEditorPermission, UserQuerySetMixin, generics.UpdateAPIView):
    """
    Docstring for ProjectUpdateAPIView
    """

    queryset = Project.objects.all()
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"

    def perform_update(self, serializer):
        instance = serializer.save()
        if not instance.content:
            instance.content = instance.titile


project_update_view = ProjectUpdateAPIView.as_view()


class ProjectDestroyAPIView(IsStaffEditorPermission, UserQuerySetMixin, generics.DestroyAPIView):
    """
    Docstring for ProjectDestroyAPIView
    """

    queryset = Project.objects.all()
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"

    def perform_destroy(self, instance):
        super().perform_destroy(instance)


project_destroy_view = ProjectDestroyAPIView.as_view()


# class ProjectListAPIView(generics.ListAPIView):
#     """
#     Docstring for ProjectListAPIView

#     GET for List
#     """

#     queryset = Project.objects.all()
#     serializer_class = PrimaryProjectSerializer


# project_list_view = ProjectListAPIView.as_view()


class CreateAPIView(mixins.CreateModelMixin, UserQuerySetMixin, generics.GenericAPIView):
    pass


class ProjectMixinView(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    generics.GenericAPIView,
):

    queryset = Project.objects.all()
    serializer_class = PrimaryProjectSerializer
    lookup_field = "pk"

    def get(self, request, *args, **kwargs):
        print(args, kwargs)
        pk = kwargs.get("pk")

        if pk is not None:
            return self.retrieve(request, *args, **kwargs)

        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):

        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        # serializer.save(user=self.request.user)
        # print(serializer.validated_data)

        # title = serializer.validated_data.get("title")
        content = serializer.validated_data.get("content")

        if content is None:
            content = "{title}"

        serializer.save(content=content)


project_mixin_view = ProjectMixinView.as_view()


@api_view(["GET", "POST"])
def project_alt_view(request, pk=None, *args, **kwargs):
    method = request.method

    if method == "GET":
        if pk is not None:
            # get request -> detail view
            # queryset = Project.objects.filter(pk=pk)
            # if not queryset.exists():
            #     raise Http404
            obj = get_object_or_404(Project, pk=pk)
            data = PrimaryProjectSerializer(obj, many=False).data
            return Response(data)

        # list view
        queryset = Project.objects.all()
        data = PrimaryProjectSerializer(queryset, many=True).data
        return Response(data)
        # url_args

    if method == "POST":
        serializer = PrimaryProjectSerializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            # instance = serializer.save()
            title = serializer.validated_data.get("title")
            content = serializer.validated_data.get("content")

            if content is None:
                content = title
            serializer.save(content=content)

            return Response({"data": serializer.data})

        return Response({"invalid": "not good data"}, status=400)
