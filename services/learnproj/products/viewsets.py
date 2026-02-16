from rest_framework import mixins, viewsets

from .models import Product
from .serializers import PrimaryProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    """
    Docstring for ProductViewSet
    get -> list -> Queryset
    get -> retrive -> Product instance detail view
    post -> create -> new instance
    put -> update
    patch -> partial update
    delete -> destroy
    """

    queryset = Product.objects.all()
    serializer_class = PrimaryProductSerializer
    lookup_field = "pk"  # default


class ProductGenericViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    Docstring for ProductGenericViewSet
    get -> list -> Queryset
    get -> retrive -> Product instance detail view
    """

    queryset = Product.objects.all()
    serializer_class = PrimaryProductSerializer
    lookup_field = "pk"  # default


product_list_view = ProductGenericViewSet.as_view({"get": "list"})
product_detail_view = ProductGenericViewSet.as_view({"get": "retrive"})
