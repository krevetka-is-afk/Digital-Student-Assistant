from apps.api.views import addItem
from django.urls import include, path

from .api_views import ApiRootView

urlpatterns = [
    path("", ApiRootView.as_view(), name="api-index"),
    path("v1/", include("config.api_v1_urls")),
    path("legacy/", include("apps.api.urls")),
    # Backward-compatible alias for old POST /api/add/.
    path("add/", addItem, name="legacy-api-add-compat"),
]
