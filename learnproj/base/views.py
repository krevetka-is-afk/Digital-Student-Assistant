from django.forms.models import model_to_dict

# from django.http import JsonResponse
from products.models import Product
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

    model_data = Product.objects.all().order_by("?").first()
    data = {}
    if model_data:
        data = model_to_dict(model_data, fields=["id", "title", "price"])
    return Response({"data": data})
