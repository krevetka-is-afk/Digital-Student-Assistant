from django.urls import path

from .views import (
    FacultyPersonDetailAPIView,
    FacultyPersonListAPIView,
    FacultyPersonProjectsAPIView,
)

urlpatterns = [
    path("persons/", FacultyPersonListAPIView.as_view(), name="faculty-person-list"),
    path(
        "persons/<path:source_key>/projects/",
        FacultyPersonProjectsAPIView.as_view(),
        name="faculty-person-projects",
    ),
    path(
        "persons/<path:source_key>/",
        FacultyPersonDetailAPIView.as_view(),
        name="faculty-person-detail",
    ),
]
