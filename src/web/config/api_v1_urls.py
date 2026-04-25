from apps.base.auth_views import VerifiedObtainAuthTokenView
from apps.base.views import health_custom, readiness
from apps.imports.views import ImportRunListCreateAPIView
from apps.outbox.views import (
    OutboxConsumerCheckpointAPIView,
    OutboxEventAckAPIView,
    OutboxEventListAPIView,
    OutboxSnapshotAPIView,
)
from apps.projects.initiative_views import (
    InitiativeProposalModerationAPIView,
    InitiativeProposalSubmitForModerationAPIView,
    initiative_proposal_list_create_view,
    initiative_proposal_rud_view,
)
from apps.projects.views import (
    ProjectModerationAPIView,
    ProjectSubmitForModerationAPIView,
    project_list_create_view,
    project_rud_view,
)
from apps.recs.views import (
    RecommendationListAPIView,
    RecommendationReindexAPIView,
    SearchProxyAPIView,
)
from apps.search.views import SearchListView
from django.urls import include, path

from .api_views import ApiV1RootView

urlpatterns = [
    path("", ApiV1RootView.as_view(), name="api-v1-root"),
    path("health/", health_custom, name="api-v1-health"),
    path("ready/", readiness, name="api-v1-ready"),
    path("auth/token/", VerifiedObtainAuthTokenView.as_view(), name="api-v1-auth-token"),
    path("search/", SearchListView.as_view(), name="api-v1-search"),
    path("recs/search/", SearchProxyAPIView.as_view(), name="api-v1-recs-search"),
    path(
        "recs/recommendations/",
        RecommendationListAPIView.as_view(),
        name="api-v1-recs-recommendations",
    ),
    path("recs/reindex/", RecommendationReindexAPIView.as_view(), name="api-v1-recs-reindex"),
    path("account/", include("apps.account.urls")),
    path("faculty/", include("apps.faculty.urls")),
    path("imports/epp/", ImportRunListCreateAPIView.as_view(), name="api-v1-import-epp"),
    path("outbox/events/", OutboxEventListAPIView.as_view(), name="api-v1-outbox-events"),
    path("outbox/snapshot/", OutboxSnapshotAPIView.as_view(), name="api-v1-outbox-snapshot"),
    path("outbox/events/ack/", OutboxEventAckAPIView.as_view(), name="api-v1-outbox-events-ack"),
    path(
        "outbox/consumers/<str:consumer>/checkpoint/",
        OutboxConsumerCheckpointAPIView.as_view(),
        name="api-v1-outbox-consumer-checkpoint",
    ),
    path(
        "initiative-proposals/",
        initiative_proposal_list_create_view,
        name="api-v1-initiative-proposal-list",
    ),
    path(
        "initiative-proposals/<int:pk>/actions/submit/",
        InitiativeProposalSubmitForModerationAPIView.as_view(),
        name="api-v1-initiative-proposal-submit",
    ),
    path(
        "initiative-proposals/<int:pk>/actions/moderate/",
        InitiativeProposalModerationAPIView.as_view(),
        name="api-v1-initiative-proposal-moderate",
    ),
    path(
        "initiative-proposals/<int:pk>/",
        initiative_proposal_rud_view,
        name="api-v1-initiative-proposal-detail",
    ),
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
