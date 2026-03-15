from apps.base.views import health_custom
from apps.projects.views import (
    ProjectModerationAPIView,
    ProjectSubmitForModerationAPIView,
    project_list_create_view,
    project_rud_view,
)
from apps.search.views import SearchListView
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

from .api_views import ApiV1RootView

urlpatterns = [
    path("", ApiV1RootView.as_view(), name="api-v1-root"),
    path("health/", health_custom, name="api-v1-health"),
    path("auth/token/", obtain_auth_token, name="api-v1-auth-token"),
    path("search/", SearchListView.as_view(), name="api-v1-search"),
    path("projects/", project_list_create_view, name="api-v1-project-list"),
    path(
        "projects/<int:pk>/actions/submit/",
        ProjectSubmitForModerationAPIView.as_view(),
        name="api-v1-project-submit",
    ),
    path(
        "projects/<int:pk>/actions/moderate/",
        ProjectModerationAPIView.as_view(),
        name="api-v1-project-moderate",
    ),
    path("projects/<int:pk>/", project_rud_view, name="api-v1-project-detail"),
    path("applications/", include("apps.applications.urls")),
    path("users/", include("apps.users.urls")),
]
