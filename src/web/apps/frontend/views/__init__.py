# Re-export all views so that urls.py (which does `from . import views`)
# continues to work without any changes.

from .auth import auth_view, logout_view, error_404, error_500
from .projects import (
    project_list,
    project_detail,
    project_create,
    project_edit,
    project_submit_moderation,
    project_delete,
)
from .applications import (
    apply_to_project,
    submit_application,
    application_list,
    project_applications,
    review_application_view,
)
from .moderation import moderation_list, moderate_project_decide
from .profile import profile_view

__all__ = [
    # auth
    "auth_view",
    "logout_view",
    "error_404",
    "error_500",
    # projects
    "project_list",
    "project_detail",
    "project_create",
    "project_edit",
    "project_submit_moderation",
    "project_delete",
    # applications
    "apply_to_project",
    "submit_application",
    "application_list",
    "project_applications",
    "review_application_view",
    # moderation
    "moderation_list",
    "moderate_project_decide",
    # profile
    "profile_view",
]
