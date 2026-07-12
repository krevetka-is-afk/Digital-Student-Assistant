from .applications.customer import (
    application_list,
    project_applications,
    review_application_view,
)
from .applications.student import (
    EditApplicationView,
    WithdrawApplicationView,
    submit_application,
)
from .auth import (
    AuthView,
    VerifyEmailView,
    logout_view,
    resend_email_code_view,
)
from .cpprp.dashboard import cpprp_dashboard
from .cpprp.deadlines import (
    cpprp_deadline_create,
    cpprp_deadline_delete,
    cpprp_deadline_toggle,
)
from .cpprp.doc_templates import (
    cpprp_template_create,
    cpprp_template_delete,
    cpprp_template_toggle,
)
from .cpprp.exports import (
    cpprp_export_applications,
    cpprp_export_projects,
    cpprp_export_projects_xlsx,
)
from .cpprp.external_access import (
    cpprp_external_allowlist_bulk_add,
    cpprp_external_allowlist_toggle,
    cpprp_external_request_approve,
    cpprp_external_request_reject,
)
from .errors import error_403, error_404, error_500
from .faculty import faculty_detail, faculty_list
from .legal import personal_data_consent_view, privacy_policy_view
from .profile import profile_view
from .projects.bookmarks import toggle_bookmark
from .projects.catalog import my_projects, project_list
from .projects.customer import (
    project_create,
    project_delete,
    project_edit,
    project_submit_moderation,
)
from .projects.detail import project_detail
from .projects.initiative import (
    initiative_moderate_decide,
    initiative_moderation_detail,
    initiative_moderation_list,
    initiative_project_create,
    initiative_proposal_delete,
    initiative_proposal_edit,
    initiative_proposal_list,
    initiative_proposal_submit,
)
from .projects.moderation import (
    moderate_project_decide,
    moderation_detail,
    moderation_list,
    moderation_update_fields,
)
from .projects.recommendations import recommendations_view
from .sse import notification_stream
from .sso import sso_hse_callback, sso_hse_redirect
from .student import student_overview
from .technologies import technology_list, technology_moderate

__all__ = [
    "AuthView",
    "VerifyEmailView",
    "resend_email_code_view",
    "logout_view",
    "error_403",
    "error_404",
    "error_500",
    "my_projects",
    "project_list",
    "project_detail",
    "project_create",
    "project_edit",
    "project_submit_moderation",
    "project_delete",
    "recommendations_view",
    "toggle_bookmark",
    "initiative_project_create",
    "initiative_proposal_list",
    "initiative_proposal_edit",
    "initiative_proposal_submit",
    "initiative_proposal_delete",
    "initiative_moderation_list",
    "initiative_moderation_detail",
    "initiative_moderate_decide",
    "faculty_list",
    "faculty_detail",
    "submit_application",
    "application_list",
    "project_applications",
    "review_application_view",
    "WithdrawApplicationView",
    "EditApplicationView",
    "cpprp_dashboard",
    "cpprp_deadline_create",
    "cpprp_deadline_toggle",
    "cpprp_deadline_delete",
    "cpprp_template_create",
    "cpprp_template_toggle",
    "cpprp_template_delete",
    "cpprp_export_projects",
    "cpprp_export_projects_xlsx",
    "cpprp_export_applications",
    "cpprp_external_allowlist_bulk_add",
    "cpprp_external_request_approve",
    "cpprp_external_request_reject",
    "cpprp_external_allowlist_toggle",
    "privacy_policy_view",
    "personal_data_consent_view",
    "moderation_list",
    "moderation_detail",
    "moderation_update_fields",
    "moderate_project_decide",
    "profile_view",
    "technology_list",
    "technology_moderate",
    "student_overview",
    "notification_stream",
    "sso_hse_redirect",
    "sso_hse_callback",
]
