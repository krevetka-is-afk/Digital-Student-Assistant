from django.urls import path

from .views import (
    AccountMeAPIView,
    CPPRPApplicationsAPIView,
    CPPRPApplicationsExportAPIView,
    CPPRPModerationQueueAPIView,
    CPPRPProjectsExportAPIView,
    CustomerApplicationsAPIView,
    CustomerProjectsAPIView,
    DocumentTemplateDownloadAPIView,
    DocumentTemplateListCreateAPIView,
    PlatformDeadlineListCreateAPIView,
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
    path(
        "cpprp/deadlines/",
        PlatformDeadlineListCreateAPIView.as_view(),
        name="account-cpprp-deadlines",
    ),
    path(
        "cpprp/templates/",
        DocumentTemplateListCreateAPIView.as_view(),
        name="account-cpprp-templates",
    ),
    path(
        "templates/<int:pk>/download/",
        DocumentTemplateDownloadAPIView.as_view(),
        name="account-template-download",
    ),
    path(
        "cpprp/export/projects/",
        CPPRPProjectsExportAPIView.as_view(),
        name="account-cpprp-export-projects",
    ),
    path(
        "cpprp/export/applications/",
        CPPRPApplicationsExportAPIView.as_view(),
        name="account-cpprp-export-applications",
    ),
]
