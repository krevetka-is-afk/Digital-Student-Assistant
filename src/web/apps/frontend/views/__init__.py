# Re-export all views so that urls.py (which does `from . import views`)
# continues to work without any changes.

from .applications import (
    application_list,
    apply_to_project,
    project_applications,
    review_application_view,
    submit_application,
)
from .auth import (
    auth_view,
    error_404,
    error_500,
    logout_view,
    resend_email_code_view,
    verify_email_view,
)
from .moderation import moderate_project_decide, moderation_list
from .profile import profile_view
from .projects import (
    project_create,
    project_delete,
    project_detail,
    project_edit,
    project_list,
    project_submit_moderation,
)

__all__ = [
    # auth
    "auth_view",
    "verify_email_view",
    "resend_email_code_view",
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
