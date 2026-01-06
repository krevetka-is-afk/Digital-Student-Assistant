import json

from django.http import JsonResponse


def api_home(request, *args, **kwargs):
    # request -> HttpRequest -> Django
    body = request.body  # byte string of JSON data
    print(request.GET)
    print(request.POST)
    data = {}
    try:
        data = json.loads(body)  # json string -> dict

    except BaseException:
        print("ERR: can not loads json")

    print(data)
    data["params"] = dict(request.GET)
    data["headers"] = dict(request.headers)  # request.META -> headers dict
    data["content_type"] = request.content_type
    return JsonResponse({"message": "Django api response", "data": data})
