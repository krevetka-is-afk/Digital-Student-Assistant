from django.urls import path

from . import views

app_name = "frontend"

urlpatterns = [
    # Auth
    path("auth/",    views.auth_view,    name="auth"),
    path("logout/",  views.logout_view,  name="logout"),

    # Projects
    path("projects/",                             views.project_list,              name="project_list"),
    path("projects/create/",                      views.project_create,            name="project_create"),
    path("projects/<int:pk>/",                    views.project_detail,            name="project_detail"),
    path("projects/<int:pk>/edit/",               views.project_edit,              name="project_edit"),
    path("projects/<int:pk>/apply/",              views.apply_to_project,          name="apply_to_project"),
    path("projects/<int:pk>/submit-application/", views.submit_application,        name="submit_application"),
    path("projects/<int:pk>/submit/",             views.project_submit_moderation, name="project_submit_moderation"),
    path("projects/<int:pk>/delete/",             views.project_delete,            name="project_delete"),

    # Applications
    path("applications/",            views.application_list,        name="application_list"),
    path("applications/<int:pk>/review/", views.review_application_view, name="review_application"),

    # Project applications (customer view)
    path("projects/<int:pk>/applications/", views.project_applications, name="project_applications"),

    # Moderation
    path("moderation/",                     views.moderation_list,          name="moderation_list"),
    path("moderation/<int:pk>/decide/",     views.moderate_project_decide,  name="moderate_project_decide"),

    # Profile
    path("profile/", views.profile_view, name="profile"),
]
