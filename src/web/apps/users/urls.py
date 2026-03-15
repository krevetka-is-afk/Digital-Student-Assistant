from django.urls import path

from .views import MyProfileAPIView

urlpatterns = [
    path("me/", MyProfileAPIView.as_view(), name="user-profile-me"),
]
