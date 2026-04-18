from django.urls import path

from .views import MyFavoriteProjectDetailAPIView, MyFavoriteProjectsAPIView, MyProfileAPIView

urlpatterns = [
    path("me/", MyProfileAPIView.as_view(), name="user-profile-me"),
    path("me/favorites/", MyFavoriteProjectsAPIView.as_view(), name="user-profile-favorites"),
    path(
        "me/favorites/<int:pk>/",
        MyFavoriteProjectDetailAPIView.as_view(),
        name="user-profile-favorite-detail",
    ),
]
