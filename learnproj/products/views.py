# from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Product
from .serializers import PrimaryProductSerializer


class ProductListCreateApiView(generics.ListCreateAPIView):
    """
    Docstring for ProductListCreateApiView

    GET for List
    POST for creation
    """

    queryset = Product.objects.all()
    serializer_class = PrimaryProductSerializer

    def perform_create(self, serializer):
        # serializer.save(user=self.request.user)
        # print(serializer.validated_data)

        title = serializer.validated_data.get("title")
        content = serializer.validated_data.get("content")

        if content is None:
            content = title

        serializer.save(content=content)
        # send django signal

        # return super().perform_create(serializer)


product_list_create_view = ProductListCreateApiView.as_view()


class ProductDetailApiView(generics.RetrieveAPIView):
    """
    Docstring for ProductDetailApiView

    GET for lookup_field
    """

    queryset = Product.objects.all()
    serializer_class = PrimaryProductSerializer
    # lookup_field = 'pk'
    # Product.objects.get(pk)


product_detail_view = ProductDetailApiView.as_view()


# class ProductListAPIView(generics.ListAPIView):
#     """
#     Docstring for ProductListAPIView

#     GET for List
#     """

#     queryset = Product.objects.all()
#     serializer_class = PrimaryProductSerializer


# product_list_view = ProductListAPIView.as_view()


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
