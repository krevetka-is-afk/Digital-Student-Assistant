"""
Application-level service functions.

Each function encapsulates a complete business operation:
  - pre-condition / authorisation checks
  - database mutation
  - Outbox event emission

Both the REST API views (apps/applications/views.py) and the SSR
frontend views (apps/frontend/views/applications.py) call these
functions instead of touching the ORM or emit_event directly.
This guarantees that every state change produces an outbox event
regardless of which entry-point triggered it.
"""

from __future__ import annotations

from apps.outbox.services import emit_event
from apps.projects.models import ProjectStatus
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Application, ApplicationStatus
from .transitions import review_application as _review_application

# ── Internal helpers ──────────────────────────────────────────────────────────


def _application_payload(application: Application) -> dict:
    """
    Serialize an Application to a plain dict suitable for an outbox payload.

    Intentionally avoids ApplicationSerializer so that this helper has no
    dependency on an HTTP request object and can be used from any context.
    """
    return {
        "id": application.pk,
        "project": application.project_id,
        "applicant": application.applicant_id,
        "status": application.status,
        "motivation": application.motivation,
        "review_comment": application.review_comment,
        "reviewed_by": application.reviewed_by_id,
        "reviewed_at": application.reviewed_at.isoformat() if application.reviewed_at else None,
        "created_at": application.created_at.isoformat() if application.created_at else None,
        "updated_at": application.updated_at.isoformat() if application.updated_at else None,
    }


def _assert_project_accepts_applications(project) -> None:
    """
    Raise ValidationError if the project cannot currently receive applications.

    Checks (in order):
      1. Project status must be catalog-visible (PUBLISHED or STAFFED).
      2. Application date window must be open.
      3. Team must not be fully staffed.
    """
    if project.status not in ProjectStatus.catalog_values():
        raise ValidationError(
            {"project": ["Applications are allowed only for projects visible in the catalog."]}
        )
    if project.application_window_state != "open":
        raise ValidationError(
            {
                "project": [
                    "Applications are allowed only while the project application window is open."
                ]
            }
        )
    if project.staffing_state == "full":
        raise ValidationError({"project": ["The project team is already full."]})


# ── Public service functions ──────────────────────────────────────────────────


def create_application(
    *,
    project,
    applicant,
    motivation: str = "",
) -> tuple[Application, bool]:
    """
    Submit a new application for *applicant* to *project*.

    Returns ``(application, created)`` where *created* is ``True`` when a new
    Application row was inserted and ``False`` when one already existed.
    An outbox event is emitted **only** on first creation.

    Raises ``ValidationError`` if the project cannot accept applications.
    """
    _assert_project_accepts_applications(project)

    application, created = Application.objects.get_or_create(
        project=project,
        applicant=applicant,
        defaults={
            "motivation": motivation,
            "status": ApplicationStatus.SUBMITTED,
        },
    )

    if created:
        emit_event(
            event_type="application.changed",
            aggregate_type="application",
            aggregate_id=application.pk,
            payload=_application_payload(application),
            idempotency_key=(
                f"application.changed:{application.pk}:{application.updated_at.isoformat()}:create"
            ),
        )

    return application, created


def delete_application(application: Application) -> None:
    """
    Delete *application* and emit a tombstone outbox event.

    The caller is responsible for authorisation (e.g. checking that the
    actor is the applicant or a staff member).
    """
    aggregate_id = application.pk
    deleted_at = timezone.now().isoformat()
    payload = {
        "id": aggregate_id,
        "project": application.project_id,
        "applicant": application.applicant_id,
        "status": "deleted",
        "tombstone": True,
        "created_at": application.created_at.isoformat() if application.created_at else None,
        "updated_at": application.updated_at.isoformat() if application.updated_at else None,
        "deleted_at": deleted_at,
    }
    application.delete()
    emit_event(
        event_type="application.deleted",
        aggregate_type="application",
        aggregate_id=aggregate_id,
        payload=payload,
        idempotency_key=f"application.deleted:{aggregate_id}:{deleted_at}",
    )


def review_application_service(
    application: Application,
    actor,
    decision: str,
    comment: str = "",
) -> Application:
    """
    Accept or reject *application* and emit an outbox event.

    Delegates all permission and business-rule checks to
    ``transitions.review_application`` (which raises ``PermissionDenied``
    or ``ValidationError`` on failure).
    """
    _review_application(application, actor, decision, comment)
    emit_event(
        event_type="application.changed",
        aggregate_type="application",
        aggregate_id=application.pk,
        payload=_application_payload(application),
        idempotency_key=(
            f"application.changed:{application.pk}:{application.updated_at.isoformat()}:review"
        ),
    )
    return application


def update_motivation(application: Application, motivation: str) -> Application:
    """
    Update the motivation text on *application* and emit an outbox event.

    The caller is responsible for checking ownership and that the application
    is still in SUBMITTED status.
    """
    application.motivation = motivation
    application.save(update_fields=["motivation", "updated_at"])
    emit_event(
        event_type="application.changed",
        aggregate_type="application",
        aggregate_id=application.pk,
        payload=_application_payload(application),
        idempotency_key=(
            f"application.changed:{application.pk}:{application.updated_at.isoformat()}:motivation"
        ),
    )
    return application
