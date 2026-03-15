from apps.users.models import UserRole
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Project, ProjectStatus


def _is_project_owner(actor, project: Project) -> bool:
    return bool(getattr(actor, "is_authenticated", False) and project.owner_id == actor.id)


def _is_cpprp_or_staff(actor) -> bool:
    if not getattr(actor, "is_authenticated", False):
        return False
    if actor.is_staff:
        return True
    try:
        profile = actor.profile
    except ObjectDoesNotExist:
        return False
    return profile.role == UserRole.CPPRP


def submit_project_for_moderation(project: Project, actor) -> Project:
    if not (_is_project_owner(actor, project) or getattr(actor, "is_staff", False)):
        raise PermissionDenied("Only the project owner or staff can submit this project.")

    if project.status not in {ProjectStatus.DRAFT, ProjectStatus.REJECTED}:
        raise ValidationError(
            {"status": ["Project can be submitted only from draft/rejected status."]}
        )

    project.status = ProjectStatus.ON_MODERATION
    project.moderation_comment = ""
    project.moderated_by = None
    project.moderated_at = None
    project.save(
        update_fields=["status", "moderation_comment", "moderated_by", "moderated_at", "updated_at"]
    )
    return project


def moderate_project(project: Project, actor, decision: str, comment: str = "") -> Project:
    if not _is_cpprp_or_staff(actor):
        raise PermissionDenied("Only CPPRP or staff can moderate projects.")

    if project.status != ProjectStatus.ON_MODERATION:
        raise ValidationError({"status": ["Project is not waiting for moderation decision."]})

    normalized_decision = decision.strip().lower()
    normalized_comment = comment.strip()
    if normalized_decision not in {"approve", "reject"}:
        raise ValidationError({"decision": ["Unsupported decision. Use 'approve' or 'reject'."]})

    if normalized_decision == "reject" and len(normalized_comment) < 20:
        raise ValidationError(
            {"comment": ["Comment is required and must be at least 20 characters for rejection."]}
        )

    project.status = (
        ProjectStatus.PUBLISHED if normalized_decision == "approve" else ProjectStatus.REJECTED
    )
    project.moderated_by = actor
    project.moderated_at = timezone.now()
    project.moderation_comment = normalized_comment
    project.save(
        update_fields=["status", "moderated_by", "moderated_at", "moderation_comment", "updated_at"]
    )

    recalculate_project_staffing(project)
    return project


def recalculate_project_staffing(project: Project) -> Project:
    from apps.applications.models import ApplicationStatus

    accepted_count = project.applications.filter(status=ApplicationStatus.ACCEPTED).count()
    status_changed = False
    next_status = project.status

    if project.status in {ProjectStatus.PUBLISHED, ProjectStatus.STAFFED}:
        next_status = (
            ProjectStatus.STAFFED
            if accepted_count >= project.team_size
            else ProjectStatus.PUBLISHED
        )
        status_changed = next_status != project.status

    if accepted_count != project.accepted_participants_count or status_changed:
        project.accepted_participants_count = accepted_count
        project.status = next_status
        project.save(update_fields=["accepted_participants_count", "status", "updated_at"])

    return project
