from apps.account.permissions import has_any_role
from apps.users.models import UserRole
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Project, ProjectSourceType, ProjectStatus


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
    if getattr(actor, "is_staff", False):
        pass
    elif not _is_project_owner(actor, project) or not has_any_role(
        actor, allowed={UserRole.CUSTOMER}, allow_staff=False
    ):
        raise PermissionDenied("Only the customer project owner or staff can submit this project.")

    if project.status not in {
        ProjectStatus.DRAFT,
        ProjectStatus.REVISION_REQUESTED,
        ProjectStatus.SUPERVISOR_REVIEW,
    }:
        raise ValidationError(
            {
                "status": [
                    "Project can be submitted only from draft, revision requested, or "
                    "supervisor review status."
                ]
            }
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

    if normalized_decision == "reject" and len(normalized_comment) < 100:
        raise ValidationError(
            {"comment": ["Comment is required and must be at least 100 characters for rejection."]}
        )

    project.status = (
        ProjectStatus.PUBLISHED
        if normalized_decision == "approve"
        else (
            ProjectStatus.REVISION_REQUESTED
            if project.source_type == ProjectSourceType.INITIATIVE
            else ProjectStatus.REJECTED
        )
    )
    project.moderated_by = actor
    project.moderated_at = timezone.now()
    project.moderation_comment = normalized_comment
    project.save(
        update_fields=["status", "moderated_by", "moderated_at", "moderation_comment", "updated_at"]
    )

    recalculate_project_staffing(project)
    return project


SOURCE_STATUS_MAPPING = {
    "Создана": ProjectStatus.CREATED,
    "Черновик": ProjectStatus.DRAFT,
    "Доработка инициатором": ProjectStatus.REVISION_REQUESTED,
    "Рассмотрение руководителем": ProjectStatus.SUPERVISOR_REVIEW,
    "Опубликована": ProjectStatus.PUBLISHED,
    "Завершена": ProjectStatus.COMPLETED,
    "Отменена": ProjectStatus.CANCELLED,
}

LOCAL_IMPORT_LOCKED_STATUSES = {
    ProjectStatus.ON_MODERATION,
    ProjectStatus.REJECTED,
    ProjectStatus.STAFFED,
}


def normalize_source_status(status_raw: str) -> str:
    normalized = SOURCE_STATUS_MAPPING.get(status_raw.strip())
    if normalized is None:
        raise ValidationError({"status_raw": [f"Unsupported source status '{status_raw}'."]})
    return normalized


def apply_imported_status(project: Project, status_raw: str) -> tuple[Project, bool]:
    next_status = normalize_source_status(status_raw)
    if project.pk and project.status in LOCAL_IMPORT_LOCKED_STATUSES:
        project.status_raw = status_raw
        return project, True

    project.status = next_status
    project.status_raw = status_raw
    return project, False


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
