from apps.account.permissions import has_any_role
from apps.users.models import UserRole
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .initiative_models import (
    InitiativeProposal,
    InitiativeProposalStatus,
    InitiativeProposalSubmission,
)
from .models import (
    Project,
    ProjectSourceType,
    ProjectStatus,
)


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


def _is_initiative_owner(actor, proposal: InitiativeProposal) -> bool:
    return bool(getattr(actor, "is_authenticated", False) and proposal.owner_id == actor.id)


def submit_initiative_proposal_for_moderation(
    proposal: InitiativeProposal, actor
) -> InitiativeProposal:
    if getattr(actor, "is_staff", False):
        pass
    elif not _is_initiative_owner(actor, proposal) or not has_any_role(
        actor, allowed={UserRole.STUDENT}, allow_staff=False
    ):
        raise PermissionDenied(
            "Only the student initiative owner or staff can submit this proposal."
        )

    if proposal.status not in {
        InitiativeProposalStatus.DRAFT,
        InitiativeProposalStatus.REVISION_REQUESTED,
    }:
        raise ValidationError(
            {
                "status": [
                    "Initiative proposal can be submitted only from draft or revision requested."
                ]
            }
        )

    with transaction.atomic():
        proposal = InitiativeProposal.objects.select_for_update().get(pk=proposal.pk)
        proposal.latest_submission_number += 1
        proposal.status = InitiativeProposalStatus.ON_MODERATION
        proposal.moderation_comment = ""
        proposal.moderated_by = None
        proposal.moderated_at = None
        proposal.save(
            update_fields=[
                "latest_submission_number",
                "status",
                "moderation_comment",
                "moderated_by",
                "moderated_at",
                "updated_at",
            ]
        )
        InitiativeProposalSubmission.objects.create(
            proposal=proposal,
            submission_number=proposal.latest_submission_number,
            snapshot=proposal.build_submission_snapshot(),
            submitted_by=actor if getattr(actor, "is_authenticated", False) else None,
        )

    return proposal


def _build_project_from_submission(
    proposal: InitiativeProposal, submission: InitiativeProposalSubmission
) -> Project:
    snapshot = submission.snapshot or proposal.build_submission_snapshot()
    tech_tags_raw = snapshot.get("tech_tags")
    participants_raw = snapshot.get("participants")
    return Project.objects.create(
        owner=None,
        title=snapshot.get("title", proposal.title),
        description=snapshot.get("description", proposal.description),
        tech_tags=list(tech_tags_raw) if isinstance(tech_tags_raw, list) else [],
        status=ProjectStatus.PUBLISHED,
        source_type=ProjectSourceType.INITIATIVE,
        source_ref=f"initiative-proposal:{proposal.pk}",
        vacancy_title=snapshot.get("title", proposal.title),
        thesis_title=snapshot.get("title", proposal.title),
        team_size=snapshot.get("team_size") or proposal.team_size,
        study_course=snapshot.get("study_course", proposal.study_course),
        education_program=snapshot.get("education_program", proposal.education_program) or "",
        supervisor_name=snapshot.get("supervisor_name", proposal.supervisor_name),
        supervisor_email=snapshot.get("supervisor_email", proposal.supervisor_email) or "",
        supervisor_department=(
            snapshot.get("supervisor_department", proposal.supervisor_department) or ""
        ),
        extra_data={
            "initiative_owner_id": proposal.owner_id,
            "initiative_participants": (
                list(participants_raw) if isinstance(participants_raw, list) else []
            ),
            "initiative_submission_number": submission.submission_number,
        },
    )


def moderate_initiative_proposal(
    proposal: InitiativeProposal, actor, decision: str, comment: str = ""
) -> InitiativeProposal:
    if not _is_cpprp_or_staff(actor):
        raise PermissionDenied("Only CPPRP or staff can moderate initiative proposals.")

    if proposal.status != InitiativeProposalStatus.ON_MODERATION:
        raise ValidationError(
            {"status": ["Initiative proposal is not waiting for moderation decision."]}
        )

    normalized_decision = decision.strip().lower()
    normalized_comment = comment.strip()
    if normalized_decision not in {"approve", "reject"}:
        raise ValidationError({"decision": ["Unsupported decision. Use 'approve' or 'reject'."]})

    if normalized_decision == "reject" and len(normalized_comment) < 50:
        raise ValidationError(
            {"comment": ["Comment is required and must be at least 50 characters for rejection."]}
        )

    with transaction.atomic():
        proposal = (
            InitiativeProposal.objects.select_for_update()
            .select_related("published_project")
            .get(pk=proposal.pk)
        )
        submission = proposal.submissions.select_for_update().order_by("-submission_number").first()
        if (
            submission is None
            or submission.decision != InitiativeProposalSubmission.Decision.PENDING
        ):
            raise ValidationError({"submission": ["No pending submission found for moderation."]})

        published_project = proposal.published_project
        if normalized_decision == "approve":
            if published_project is not None:
                raise ValidationError(
                    {"published_project": ["Initiative proposal has already been published."]}
                )
            published_project = _build_project_from_submission(proposal, submission)
            proposal.status = InitiativeProposalStatus.PUBLISHED
            proposal.published_project = published_project
            submission.decision = InitiativeProposalSubmission.Decision.APPROVED
        else:
            proposal.status = InitiativeProposalStatus.REVISION_REQUESTED
            submission.decision = InitiativeProposalSubmission.Decision.REJECTED

        proposal.moderated_by = actor
        proposal.moderated_at = timezone.now()
        proposal.moderation_comment = normalized_comment
        proposal.save(
            update_fields=[
                "status",
                "published_project",
                "moderated_by",
                "moderated_at",
                "moderation_comment",
                "updated_at",
            ]
        )

        submission.comment = normalized_comment
        submission.reviewed_by = actor
        submission.reviewed_at = proposal.moderated_at
        submission.published_project = published_project
        submission.save(
            update_fields=[
                "decision",
                "comment",
                "reviewed_by",
                "reviewed_at",
                "published_project",
            ]
        )

    return proposal
