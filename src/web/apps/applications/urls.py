from django.urls import path

from .views import (
    ApplicationListCreateAPIView,
    ApplicationRetrieveUpdateDestroyAPIView,
    ApplicationReviewAPIView,
)

urlpatterns = [
    path("", ApplicationListCreateAPIView.as_view(), name="application-list"),
    path("<int:pk>/actions/review/", ApplicationReviewAPIView.as_view(), name="application-review"),
    path("<int:pk>/", ApplicationRetrieveUpdateDestroyAPIView.as_view(), name="application-detail"),
]
