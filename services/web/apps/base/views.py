# from django.http import JsonResponse
from apps.products.serializers import PrimaryProductSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response

# from django.http import JsonResponse # need to set cookie


@api_view(["POST"])
def api_home(request, *args, **kwargs):
    """
    Docstring for api_home

    :param request: Description
    :param args: Description
    :param kwargs: Description
    """

    # if request.method != "POST":
    #     return Response({"detail": "GET method not allowed"}, status=405)

    serializer = PrimaryProductSerializer(data=request.data)
    if serializer.is_valid(raise_exception=True):
        # instance = serializer.save()
        print(serializer.data)
        return Response({"data": serializer.data})
    return Response({"invalid": "not good data"}, status=400)


@api_view(["GET"])
def health_custom(request, *args, **kwargs):
    return Response({"status": "ok", "service": "web"})
