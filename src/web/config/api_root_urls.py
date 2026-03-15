from apps.api.views import addItem
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .api_views import ApiRootView

urlpatterns = [
    path("", ApiRootView.as_view(), name="api-index"),
    path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("v1/", include("config.api_v1_urls")),
    path("legacy/", include("apps.api.urls")),
    # Backward-compatible alias for old POST /api/add/.
    path("add/", addItem, name="legacy-api-add-compat"),
]
