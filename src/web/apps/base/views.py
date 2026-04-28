# from django.http import JsonResponse
from apps.base.metrics import metrics_response, set_readiness_check
from apps.projects.serializers import PrimaryProjectSerializer
from django.db import connections
from django.db.utils import Error as DatabaseError
from django.shortcuts import render
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

# from django.http import JsonResponse # need to set cookie


@extend_schema(exclude=True)
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

    serializer = PrimaryProjectSerializer(data=request.data)
    if serializer.is_valid(raise_exception=True):
        # instance = serializer.save()
        print(serializer.data)
        return Response({"data": serializer.data})
    return Response({"invalid": "not good data"}, status=400)


@extend_schema(exclude=True)
@api_view(["GET"])
def health_custom(request, *args, **kwargs):
    return Response({"status": "ok"})


@extend_schema(exclude=True)
@api_view(["GET"])
def readiness(request, *args, **kwargs):
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        set_readiness_check(check="database", healthy=False)
        return Response(
            {"status": "degraded", "checks": {"database": "down"}},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    set_readiness_check(check="database", healthy=True)
    return Response({"status": "ok", "checks": {"database": "up"}})


@extend_schema(exclude=True)
@api_view(["GET"])
def metrics(request, *args, **kwargs):
    return metrics_response()


def home_page(request, *args, **kwargs):
    return render(request, "home.html")
