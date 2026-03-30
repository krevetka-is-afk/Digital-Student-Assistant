import json
from uuid import uuid4

from apps.projects.models import (
    InitiativeProposal,
    InitiativeProposalStatus,
    InitiativeProposalSubmission,
    Project,
    ProjectSourceType,
    ProjectStatus,
)
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def _make_user(*, role: str | None = None, is_staff: bool = False):
    username = f"initiative-{uuid4().hex[:8]}"
    user = get_user_model().objects.create_user(
        username=username,
        password="placeholder",
        is_staff=is_staff,
    )
    if role is not None:
        UserProfile.objects.create(user=user, role=role)
    return user


def _proposal_payload(title: str | None = None) -> dict:
    return {
        "title": title or f"Initiative {uuid4().hex[:8]}",
        "description": "Initiative proposal for an applied research topic.",
        "tech_tags": ["Python", "ML"],
        "team_size": 2,
        "study_course": 4,
        "education_program": "AI Systems",
        "supervisor_name": "Dr. External Supervisor",
        "supervisor_email": "supervisor@example.com",
        "supervisor_department": "External Lab",
        "participants": [
            {
                "full_name": "Alice Example",
                "email": "alice@example.com",
                "study_course": 4,
                "education_program": "AI Systems",
                "is_external": False,
            },
            {
                "full_name": "Bob External",
                "email": "bob.external@example.com",
                "education_program": "Partner University",
                "is_external": True,
            },
        ],
    }


def test_student_can_create_initiative_proposal_draft():
    student = _make_user(role=UserRole.STUDENT)
    client = Client()
    client.force_login(student)

    response = client.post(
        reverse("api-v1-initiative-proposal-list"),
        data=json.dumps(_proposal_payload()),
        content_type="application/json",
    )

    assert response.status_code == 201
    payload = response.json()
    proposal = InitiativeProposal.objects.get(pk=payload["id"])
    assert proposal.owner_id == student.id
    assert proposal.status == InitiativeProposalStatus.DRAFT
    assert proposal.supervisor_name == "Dr. External Supervisor"
    assert len(proposal.participants) == 2
    assert payload["latest_submission_number"] == 0
    assert payload["submission_history"] == []


def test_reject_requires_comment_with_minimum_length():
    student = _make_user(role=UserRole.STUDENT)
    cpprp = _make_user(role=UserRole.CPPRP)
    proposal = InitiativeProposal.objects.create(
        owner=student,
        status=InitiativeProposalStatus.ON_MODERATION,
        **_proposal_payload(title=f"Rejected {uuid4().hex[:8]}"),
    )
    InitiativeProposalSubmission.objects.create(
        proposal=proposal,
        submission_number=1,
        snapshot=proposal.build_submission_snapshot(),
        submitted_by=student,
    )
    proposal.latest_submission_number = 1
    proposal.save(update_fields=["latest_submission_number", "updated_at"])

    client = Client()
    client.force_login(cpprp)
    response = client.post(
        reverse("api-v1-initiative-proposal-moderate", kwargs={"pk": proposal.pk}),
        data=json.dumps({"decision": "reject", "comment": "too short"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "comment" in response.json()


def test_reject_edit_and_resubmit_preserves_submission_history():
    student = _make_user(role=UserRole.STUDENT)
    cpprp = _make_user(role=UserRole.CPPRP)
    client = Client()
    client.force_login(student)

    create_response = client.post(
        reverse("api-v1-initiative-proposal-list"),
        data=json.dumps(_proposal_payload(title="Initial initiative title")),
        content_type="application/json",
    )
    assert create_response.status_code == 201
    proposal_id = create_response.json()["id"]

    submit_response = client.post(
        reverse("api-v1-initiative-proposal-submit", kwargs={"pk": proposal_id})
    )
    assert submit_response.status_code == 200

    moderator_client = Client()
    moderator_client.force_login(cpprp)
    reject_comment = (
        "Please clarify the hypothesis, expected artifacts, success metrics, "
        "and the supervisor participation model before resubmission."
    )
    reject_response = moderator_client.post(
        reverse("api-v1-initiative-proposal-moderate", kwargs={"pk": proposal_id}),
        data=json.dumps({"decision": "reject", "comment": reject_comment}),
        content_type="application/json",
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == InitiativeProposalStatus.REVISION_REQUESTED

    updated_title = "Reworked initiative title"
    patch_response = client.patch(
        reverse("api-v1-initiative-proposal-detail", kwargs={"pk": proposal_id}),
        data=json.dumps(
            {
                "title": updated_title,
                "description": "Expanded proposal after moderation feedback.",
            }
        ),
        content_type="application/json",
    )
    assert patch_response.status_code == 200

    resubmit_response = client.post(
        reverse("api-v1-initiative-proposal-submit", kwargs={"pk": proposal_id})
    )
    assert resubmit_response.status_code == 200

    proposal = InitiativeProposal.objects.get(pk=proposal_id)
    history = list(proposal.submissions.order_by("submission_number"))
    assert proposal.status == InitiativeProposalStatus.ON_MODERATION
    assert proposal.latest_submission_number == 2
    assert len(history) == 2
    assert history[0].decision == InitiativeProposalSubmission.Decision.REJECTED
    assert history[0].comment == reject_comment
    assert history[0].snapshot["title"] == "Initial initiative title"
    assert history[1].decision == InitiativeProposalSubmission.Decision.PENDING
    assert history[1].snapshot["title"] == updated_title


def test_approve_publishes_initiative_as_catalog_project():
    student = _make_user(role=UserRole.STUDENT)
    cpprp = _make_user(role=UserRole.CPPRP)
    client = Client()
    client.force_login(student)

    create_response = client.post(
        reverse("api-v1-initiative-proposal-list"),
        data=json.dumps(_proposal_payload(title="Catalog initiative")),
        content_type="application/json",
    )
    assert create_response.status_code == 201
    proposal_id = create_response.json()["id"]

    submit_response = client.post(
        reverse("api-v1-initiative-proposal-submit", kwargs={"pk": proposal_id})
    )
    assert submit_response.status_code == 200

    moderator_client = Client()
    moderator_client.force_login(cpprp)
    approve_response = moderator_client.post(
        reverse("api-v1-initiative-proposal-moderate", kwargs={"pk": proposal_id}),
        data=json.dumps({"decision": "approve"}),
        content_type="application/json",
    )

    assert approve_response.status_code == 200
    payload = approve_response.json()
    assert payload["status"] == InitiativeProposalStatus.PUBLISHED
    assert payload["published_project"] is not None

    proposal = InitiativeProposal.objects.select_related("published_project").get(pk=proposal_id)
    project = proposal.published_project
    assert project is not None
    assert project.status == ProjectStatus.PUBLISHED
    assert project.source_type == ProjectSourceType.INITIATIVE
    assert project.source_ref == f"initiative-proposal:{proposal.pk}"
    assert project.supervisor_name == proposal.supervisor_name
    assert project.extra_data["initiative_participants"] == proposal.participants
    assert project.extra_data["initiative_submission_number"] == 1

    submission = proposal.submissions.get(submission_number=1)
    assert submission.decision == InitiativeProposalSubmission.Decision.APPROVED
    assert submission.published_project_id == project.pk
    assert Project.objects.filter(pk=project.pk, source_type=ProjectSourceType.INITIATIVE).exists()
