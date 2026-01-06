# from django.http import JsonResponse
from products.models import Product
from products.serializers import PrimaryProductSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def api_home(request, *args, **kwargs):
    """
    Docstring for api_home

    :param request: Description
    :param args: Description
    :param kwargs: Description
    """

    # if request.method != "POST":
    #     return Response({"detail": "GET method not allowed"}, status=405)

    instance = Product.objects.all().order_by("?").first()
    data = {}
    if instance:
        # data = model_to_dict(instance, fields=["id", "title", "price"])
        data = PrimaryProductSerializer(instance).data
    return Response({"data": data})
