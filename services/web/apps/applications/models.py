from apps.projects.models import Project
from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class ApplicationStatus(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"


class Application(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="applications",
        verbose_name="Project",
        help_text="Project that this application targets.",
    )
    applicant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="project_applications",
        verbose_name="Applicant",
        help_text="Student user who submitted the application.",
    )
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.SUBMITTED,
        db_index=True,
        verbose_name="Status",
        help_text="Current status of application review.",
    )
    motivation = models.TextField(
        blank=True,
        verbose_name="Motivation",
        help_text="Free-text motivation from the applicant.",
    )
    review_comment = models.TextField(
        blank=True,
        default="",
        verbose_name="Review comment",
        help_text="Teacher/CPPRP decision comment.",
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="reviewed_applications",
        null=True,
        blank=True,
        verbose_name="Reviewed by",
        help_text="User who reviewed this application.",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Reviewed at",
        help_text="Timestamp of the application review decision.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Created at",
        help_text="Timestamp when application was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated at",
        help_text="Timestamp of the latest application update.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "applicant"],
                name="applications_unique_project_applicant",
            )
        ]
        indexes = [
            models.Index(fields=["status", "created_at"], name="appl_status_created_idx"),
            models.Index(
                fields=["applicant", "created_at"],
                name="appl_applicant_created_idx",
            ),
        ]
        ordering = ["-created_at"]
        verbose_name = "Application"
        verbose_name_plural = "Applications"

    def __str__(self) -> str:
        return f"Application #{self.pk} ({self.status})"
