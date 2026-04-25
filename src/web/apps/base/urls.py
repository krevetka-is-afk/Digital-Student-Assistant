from django.urls import path
from health_check.views import HealthCheckView

from . import views
from .auth_views import VerifiedObtainAuthTokenView

urlpatterns = [
    path("auth/", VerifiedObtainAuthTokenView.as_view()),
    path("", views.api_home, name="api-home"),
    path(
        "health/",
        HealthCheckView.as_view(
            # checks=[],
        ),
        name="health",
    ),
    path("health_custom/", views.health_custom, name="health_custom"),
]
