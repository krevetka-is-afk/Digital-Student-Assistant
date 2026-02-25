# from django.http import Http404
from apps.base.mixins import StaffEditorPermissionMixin, UserQuerySetMixin
from apps.base.permissions import IsStaffEditorPermission
from django.shortcuts import get_object_or_404
from rest_framework import generics, mixins
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Product
from .serializers import PrimaryProductSerializer


class ProductListCreateAPIView(
    generics.ListCreateAPIView, UserQuerySetMixin, StaffEditorPermissionMixin
):
    """
    Docstring for ProductListCreateAPIView

    GET for List
    POST for creation
    """

    queryset = Product.objects.all()
    serializer_class = PrimaryProductSerializer

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
    #         return Product.objects.none()

    #     return qs.filter(user=request.user)


product_list_create_view = ProductListCreateAPIView.as_view()


class ProductDetailAPIView(StaffEditorPermissionMixin, UserQuerySetMixin, generics.RetrieveAPIView):
    """
    Docstring for ProductDetailAPIView

    GET for lookup_field
    """

    queryset = Product.objects.all()
    serializer_class = PrimaryProductSerializer
    # lookup_field = 'pk'
    # Product.objects.get(pk)


product_detail_view = ProductDetailAPIView.as_view()


class ProductUpdateAPIView(IsStaffEditorPermission, UserQuerySetMixin, generics.UpdateAPIView):
    """
    Docstring for ProductUpdateAPIView
    """

    queryset = Product.objects.all()
    serializer_class = PrimaryProductSerializer
    lookup_field = "pk"

    def perform_update(self, serializer):
        instance = serializer.save()
        if not instance.content:
            instance.content = instance.titile


product_update_view = ProductUpdateAPIView.as_view()


class ProductDestroyAPIView(IsStaffEditorPermission, UserQuerySetMixin, generics.DestroyAPIView):
    """
    Docstring for ProductDestroyAPIView
    """

    queryset = Product.objects.all()
    serializer_class = PrimaryProductSerializer
    lookup_field = "pk"

    def perform_destroy(self, instance):
        super().perform_destroy(instance)


product_destroy_view = ProductDestroyAPIView.as_view()


# class ProductListAPIView(generics.ListAPIView):
#     """
#     Docstring for ProductListAPIView

#     GET for List
#     """

#     queryset = Product.objects.all()
#     serializer_class = PrimaryProductSerializer


# product_list_view = ProductListAPIView.as_view()


class CreateAPIView(mixins.CreateModelMixin, UserQuerySetMixin, generics.GenericAPIView):
    pass


class ProductMixinView(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    generics.GenericAPIView,
):

    queryset = Product.objects.all()
    serializer_class = PrimaryProductSerializer
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


product_mixin_view = ProductMixinView.as_view()


@api_view(["GET", "POST"])
def product_alt_view(request, pk=None, *args, **kwargs):
    method = request.method

    if method == "GET":
        if pk is not None:
            # get request -> detail view
            # queryset = Product.objects.filter(pk=pk)
            # if not queryset.exists():
            #     raise Http404
            obj = get_object_or_404(Product, pk=pk)
            data = PrimaryProductSerializer(obj, many=False).data
            return Response(data)

        # list view
        queryset = Product.objects.all()
        data = PrimaryProductSerializer(queryset, many=True).data
        return Response(data)
        # url_args

    if method == "POST":
        serializer = PrimaryProductSerializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            # instance = serializer.save()
            title = serializer.validated_data.get("title")
            content = serializer.validated_data.get("content")

            if content is None:
                content = title
            serializer.save(content=content)

            return Response({"data": serializer.data})

        return Response({"invalid": "not good data"}, status=400)
