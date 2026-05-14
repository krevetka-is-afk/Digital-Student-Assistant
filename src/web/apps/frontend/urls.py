from django.urls import path

from . import views

app_name = "frontend"

urlpatterns = [
    # Legal
    path("legal/privacy/", views.privacy_policy_view, name="privacy_policy"),
    path("legal/consent/", views.personal_data_consent_view, name="personal_data_consent"),

    # Auth
    path("auth/", views.auth_view, name="auth"),
    path("auth/verify/", views.verify_email_view, name="verify_email"),
    path("auth/verify/resend/", views.resend_email_code_view, name="resend_email_code"),
    path("logout/", views.logout_view, name="logout"),

    # Projects
    path("projects/", views.project_list, name="project_list"),
    path("projects/create/", views.project_create, name="project_create"),
    path("projects/<int:pk>/", views.project_detail, name="project_detail"),
    path("projects/<int:pk>/edit/", views.project_edit, name="project_edit"),
    path("projects/<int:pk>/apply/", views.apply_to_project, name="apply_to_project"),
    path(
        "projects/<int:pk>/submit-application/",
        views.submit_application,
        name="submit_application",
    ),
    path(
        "projects/<int:pk>/submit/",
        views.project_submit_moderation,
        name="project_submit_moderation",
    ),
    path("projects/<int:pk>/delete/", views.project_delete, name="project_delete"),
    path("projects/<int:pk>/bookmark/", views.toggle_bookmark, name="toggle_bookmark"),
    path(
        "projects/initiative/",
        views.initiative_project_create,
        name="initiative_project_create",
    ),

    # Applications
    path("applications/", views.application_list, name="application_list"),
    path(
        "applications/<int:pk>/review/",
        views.review_application_view,
        name="review_application",
    ),
    path(
        "applications/<int:pk>/withdraw/",
        views.withdraw_application,
        name="withdraw_application",
    ),
    path(
        "applications/<int:pk>/edit/",
        views.edit_application,
        name="edit_application",
    ),

    # Project applications (customer view)
    path(
        "projects/<int:pk>/applications/",
        views.project_applications,
        name="project_applications",
    ),

    # Technologies directory
    path("technologies/", views.technology_list, name="technology_list"),
    path("technologies/<int:pk>/moderate/", views.technology_moderate, name="technology_moderate"),

    # CPPRP administration dashboard
    path("cpprp/", views.cpprp_dashboard, name="cpprp_dashboard"),
    path("cpprp/deadlines/create/", views.cpprp_deadline_create, name="cpprp_deadline_create"),
    path(
        "cpprp/deadlines/<int:pk>/toggle/",
        views.cpprp_deadline_toggle,
        name="cpprp_deadline_toggle"
    ),
    path(
        "cpprp/deadlines/<int:pk>/delete/",
        views.cpprp_deadline_delete,
        name="cpprp_deadline_delete"
    ),
    path(
        "cpprp/templates/create/",
        views.cpprp_template_create,
        name="cpprp_template_create"
    ),
    path(
        "cpprp/templates/<int:pk>/toggle/",
        views.cpprp_template_toggle,
        name="cpprp_template_toggle"),
    path(
        "cpprp/templates/<int:pk>/delete/",
        views.cpprp_template_delete,
        name="cpprp_template_delete"
    ),
    path(
        "cpprp/external-access/allow/",
        views.cpprp_external_allowlist_bulk_add,
        name="cpprp_external_allowlist_bulk_add",
    ),
    path(
        "cpprp/external-access/allowlist/<int:pk>/toggle/",
        views.cpprp_external_allowlist_toggle,
        name="cpprp_external_allowlist_toggle",
    ),
    path(
        "cpprp/external-access/requests/<int:pk>/approve/",
        views.cpprp_external_request_approve,
        name="cpprp_external_request_approve",
    ),
    path(
        "cpprp/external-access/requests/<int:pk>/reject/",
        views.cpprp_external_request_reject,
        name="cpprp_external_request_reject",
    ),
    path("cpprp/export/projects/", views.cpprp_export_projects, name="cpprp_export_projects"),
    path(
        "cpprp/export/projects.xlsx",
        views.cpprp_export_projects_xlsx,
        name="cpprp_export_projects_xlsx",
    ),
    path(
        "cpprp/export/applications/",
        views.cpprp_export_applications,
        name="cpprp_export_applications"
    ),

    # Moderation
    path("moderation/", views.moderation_list, name="moderation_list"),
    path(
        "moderation/<int:pk>/decide/",
        views.moderate_project_decide,
        name="moderate_project_decide",
    ),

    # Student overview / dashboard
    path("student/", views.student_overview, name="student_overview"),

    # Recommendations (student only)
    path("recommendations/", views.recommendations_view, name="recommendations"),

    # Profile
    path("profile/", views.profile_view, name="profile"),
]
