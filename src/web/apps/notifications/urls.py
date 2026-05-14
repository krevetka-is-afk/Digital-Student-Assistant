from django.urls import path

from .views import (
    NotificationListAPIView,
    NotificationMarkReadAPIView,
    NotificationUnreadCountAPIView,
)

urlpatterns = [
    path("", NotificationListAPIView.as_view(), name="api-v1-notification-list"),
    path(
        "mark-read/",
        NotificationMarkReadAPIView.as_view(),
        name="api-v1-notification-mark-read",
    ),
    path(
        "unread-count/",
        NotificationUnreadCountAPIView.as_view(),
        name="api-v1-notification-unread-count",
    ),
]
