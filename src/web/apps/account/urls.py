from django.urls import path

from .views import (
    AccountMeAPIView,
    CPPRPApplicationsAPIView,
    CPPRPModerationQueueAPIView,
    CustomerApplicationsAPIView,
    CustomerProjectsAPIView,
    StudentOverviewAPIView,
)

urlpatterns = [
    path("me/", AccountMeAPIView.as_view(), name="account-me"),
    path("student/overview/", StudentOverviewAPIView.as_view(), name="account-student-overview"),
    path("customer/projects/", CustomerProjectsAPIView.as_view(), name="account-customer-projects"),
    path(
        "customer/applications/",
        CustomerApplicationsAPIView.as_view(),
        name="account-customer-applications",
    ),
    path(
        "cpprp/moderation-queue/",
        CPPRPModerationQueueAPIView.as_view(),
        name="account-cpprp-moderation-queue",
    ),
    path(
        "cpprp/applications/",
        CPPRPApplicationsAPIView.as_view(),
        name="account-cpprp-applications",
    ),
]
