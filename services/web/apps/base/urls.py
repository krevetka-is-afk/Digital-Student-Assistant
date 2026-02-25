from debug_toolbar.toolbar import debug_toolbar_urls
from django.urls import path
from health_check.views import HealthCheckView
from rest_framework.authtoken.views import obtain_auth_token

from . import views

urlpatterns = [
    path("auth/", obtain_auth_token),
    path("", views.api_home, name="api-home"),
    path(
        "health/",
        HealthCheckView.as_view(
            # checks=[],
        ),
        name="health",
    ),
    path("health_custom/", views.health_custom, name="health_custom"),
] + debug_toolbar_urls()
