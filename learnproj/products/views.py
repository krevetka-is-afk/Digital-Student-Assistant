from rest_framework import generics

from .models import Product
from .serializers import PrimaryProductSerializer


class ProductDetailApiView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = PrimaryProductSerializer
    # lookup_field = 'pk'
    # Product.objects.get(pk)


product_detail_view = ProductDetailApiView.as_view()
