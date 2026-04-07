from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class InitiativeProposalStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ON_MODERATION = "on_moderation", "On moderation"
    REVISION_REQUESTED = "revision_requested", "Revision requested"
    PUBLISHED = "published", "Published"


class InitiativeProposal(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="initiative_proposals",
        verbose_name="Owner",
        help_text="Student owner who authored the initiative proposal.",
    )
    title = models.CharField(
        max_length=255,
        verbose_name="Title",
        help_text="Initiative topic title.",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Detailed initiative proposal description.",
    )
    tech_tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Tech tags",
        help_text="Technology tags specified by the proposal author.",
    )
    team_size = models.PositiveIntegerField(
        default=1,
        verbose_name="Team size",
        help_text="Number of participants expected for the initiative topic.",
    )
    study_course = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Study course",
        help_text="Recommended study course for the initiative topic.",
    )
    education_program = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Education program",
        help_text="Recommended education program for the initiative topic.",
    )
    supervisor_name = models.CharField(
        max_length=255,
        verbose_name="Supervisor name",
        help_text="Scientific supervisor full name. Can reference a person outside the system.",
    )
    supervisor_email = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Supervisor email",
        help_text="Scientific supervisor email when available.",
    )
    supervisor_department = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Supervisor department",
        help_text="Scientific supervisor department or affiliation.",
    )
    participants = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Participants",
        help_text="Participants attached to the proposal, including people outside the system.",
    )
    status = models.CharField(
        max_length=32,
        choices=InitiativeProposalStatus.choices,
        default=InitiativeProposalStatus.DRAFT,
        db_index=True,
        verbose_name="Status",
        help_text="Current initiative proposal workflow state.",
    )
    latest_submission_number = models.PositiveIntegerField(
        default=0,
        verbose_name="Latest submission number",
        help_text="Sequential counter of moderation submissions for history tracking.",
    )
    moderated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="moderated_initiative_proposals",
        null=True,
        blank=True,
        verbose_name="Moderated by",
        help_text="User who made the latest moderation decision.",
    )
    moderated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Moderated at",
        help_text="Timestamp of the latest moderation decision.",
    )
    moderation_comment = models.TextField(
        blank=True,
        default="",
        verbose_name="Moderation comment",
        help_text="Latest CPPRP moderation comment.",
    )
    published_project = models.OneToOneField(
        "projects.Project",
        on_delete=models.SET_NULL,
        related_name="initiative_proposal",
        null=True,
        blank=True,
        verbose_name="Published project",
        help_text="Catalog project created from this initiative proposal after approval.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Created at",
        help_text="Timestamp when the initiative proposal was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated at",
        help_text="Timestamp of the latest initiative proposal update.",
    )

    class Meta:
        indexes = [
            models.Index(fields=["owner", "status"], name="initiative_owner_status_idx"),
            models.Index(fields=["status", "updated_at"], name="initiative_status_updated_idx"),
        ]
        ordering = ["-created_at"]
        verbose_name = "Initiative proposal"
        verbose_name_plural = "Initiative proposals"

    def __str__(self) -> str:
        return self.title

    def build_submission_snapshot(self) -> dict[str, object]:
        return {
            "title": self.title,
            "description": self.description,
            "tech_tags": list(self.tech_tags or []),
            "team_size": self.team_size,
            "study_course": self.study_course,
            "education_program": self.education_program,
            "supervisor_name": self.supervisor_name,
            "supervisor_email": self.supervisor_email,
            "supervisor_department": self.supervisor_department,
            "participants": list(self.participants or []),
        }


class InitiativeProposalSubmission(models.Model):
    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    proposal = models.ForeignKey(
        InitiativeProposal,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Proposal",
        help_text="Initiative proposal version submitted to CPPRP.",
    )
    submission_number = models.PositiveIntegerField(
        verbose_name="Submission number",
        help_text="Sequential proposal submission number.",
    )
    snapshot = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Snapshot",
        help_text="Submitted proposal snapshot preserved for history.",
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="initiative_proposal_submissions",
        null=True,
        blank=True,
        verbose_name="Submitted by",
        help_text="Actor who submitted this revision.",
    )
    submitted_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Submitted at",
        help_text="Timestamp when this revision was submitted to CPPRP.",
    )
    decision = models.CharField(
        max_length=20,
        choices=Decision.choices,
        default=Decision.PENDING,
        db_index=True,
        verbose_name="Decision",
        help_text="Moderation decision for this submitted revision.",
    )
    comment = models.TextField(
        blank=True,
        default="",
        verbose_name="Comment",
        help_text="CPPRP moderation comment for this submission.",
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="reviewed_initiative_submissions",
        null=True,
        blank=True,
        verbose_name="Reviewed by",
        help_text="CPPRP/staff user who reviewed the submission.",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Reviewed at",
        help_text="Timestamp when moderation decision was made for this submission.",
    )
    published_project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        related_name="initiative_publication_submissions",
        null=True,
        blank=True,
        verbose_name="Published project",
        help_text="Catalog project created after approval of this submission.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "submission_number"],
                name="initiative_submission_unique_number",
            )
        ]
        indexes = [
            models.Index(fields=["proposal", "submitted_at"], name="initiative_submission_time_idx")
        ]
        ordering = ["submission_number"]
        verbose_name = "Initiative proposal submission"
        verbose_name_plural = "Initiative proposal submissions"

    def __str__(self) -> str:
        return f"Initiative proposal #{self.proposal_id} submission {self.submission_number}"
