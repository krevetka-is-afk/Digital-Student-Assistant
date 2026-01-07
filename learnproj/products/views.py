from rest_framework import generics

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


class ProductListAPIView(generics.ListAPIView):
    """
    Docstring for ProductListAPIView

    GET for List
    """

    queryset = Product.objects.all()
    serializer_class = PrimaryProductSerializer


product_list_view = ProductListAPIView.as_view()
