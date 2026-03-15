from apps.projects.transitions import recalculate_project_staffing
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Application, ApplicationStatus


def _can_review_application(actor, application: Application) -> bool:
    if not getattr(actor, "is_authenticated", False):
        return False
    if actor.is_staff:
        return True
    return application.project.owner_id == actor.id


def review_application(
    application: Application, actor, decision: str, comment: str = ""
) -> Application:
    if not _can_review_application(actor, application):
        raise PermissionDenied("Only project owner or staff can review applications.")

    if application.status != ApplicationStatus.SUBMITTED:
        raise ValidationError({"status": ["Only submitted applications can be reviewed."]})

    normalized_decision = decision.strip().lower()
    normalized_comment = comment.strip()
    if normalized_decision not in {"accept", "reject"}:
        raise ValidationError({"decision": ["Unsupported decision. Use 'accept' or 'reject'."]})

    if normalized_decision == "reject" and len(normalized_comment) < 20:
        raise ValidationError(
            {"comment": ["Comment is required and must be at least 20 characters for rejection."]}
        )

    application.status = (
        ApplicationStatus.ACCEPTED
        if normalized_decision == "accept"
        else ApplicationStatus.REJECTED
    )
    application.review_comment = normalized_comment
    application.reviewed_by = actor
    application.reviewed_at = timezone.now()
    application.save(
        update_fields=["status", "review_comment", "reviewed_by", "reviewed_at", "updated_at"]
    )

    recalculate_project_staffing(application.project)
    return application
