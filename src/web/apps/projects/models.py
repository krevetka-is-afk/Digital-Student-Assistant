from django.conf import settings
from django.db import models
from django.db.models import Q

User = settings.AUTH_USER_MODEL


class ProjectStatus(models.TextChoices):
    CREATED = "created", "Created"
    DRAFT = "draft", "Draft"
    REVISION_REQUESTED = "revision_requested", "Revision requested"
    SUPERVISOR_REVIEW = "supervisor_review", "Supervisor review"
    ON_MODERATION = "on_moderation", "On moderation"
    PUBLISHED = "published", "Published"
    REJECTED = "rejected", "Rejected"
    STAFFED = "staffed", "Staffed"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"
    ARCHIVED = "archived", "Archived"

    @classmethod
    def catalog_values(cls) -> tuple[str, ...]:
        return (cls.PUBLISHED, cls.STAFFED)


class ProjectSourceType(models.TextChoices):
    SUPERVISOR = "supervisor", "Supervisor"
    INITIATIVE = "initiative", "Initiative"
    EPP = "epp", "EPP"
    MANUAL = "manual", "Manual"


class ProjectQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status__in=ProjectStatus.catalog_values())

    def search(self, query, user=None):
        lookup = Q(title__icontains=query) | Q(description__icontains=query)
        qs = self.published().filter(lookup)
        if user is not None and getattr(user, "is_authenticated", False):
            qs2 = self.filter(owner=user).filter(lookup)
            qs = (qs | qs2).distinct()
        return qs


class ProjectManager(models.Manager.from_queryset(ProjectQuerySet)):
    pass


class Project(models.Model):
    title = models.CharField(
        max_length=255,
        verbose_name="Title",
        help_text="Human-readable project title shown in catalog and API lists.",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Short project description and context for students.",
    )
    tech_tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Tech tags",
        help_text="Technology tags as JSON list (temporary MVP storage format).",
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="owned_projects",
        null=True,
        verbose_name="Owner",
        help_text="Project owner (mentor/customer) who created this project.",
    )
    status = models.CharField(
        max_length=20,
        choices=ProjectStatus.choices,
        default=ProjectStatus.DRAFT,
        db_index=True,
        verbose_name="Status",
        help_text="Publishing lifecycle state used in filters and workflows.",
    )
    team_size = models.PositiveIntegerField(
        default=1,
        verbose_name="Team size",
        help_text="Number of students needed for this project.",
    )
    accepted_participants_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Accepted participants count",
        help_text="Current number of accepted student applications.",
    )
    source_type = models.CharField(
        max_length=20,
        choices=ProjectSourceType.choices,
        default=ProjectSourceType.MANUAL,
        db_index=True,
        verbose_name="Source type",
        help_text="Data source of the project (sheet/import/manual).",
    )
    source_ref = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Source reference",
        help_text="External source identifier (sheet row key, EPP id, etc.).",
    )
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Extra data",
        help_text="Unstructured source-specific payload for hybrid MVP model.",
    )
    moderated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="moderated_projects",
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
        help_text="Reason/comment for moderation decision.",
    )
    supervisor_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Supervisor name",
        help_text="Optional desired supervisor for student initiative projects.",
    )

    # --- EPP display fields (synced with main branch) ---
    study_course = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Study course",
        help_text="Recommended course for applicants when known.",
    )
    education_program = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Education program",
        help_text="Recommended education program or OP for applicants.",
    )
    application_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="Application deadline",
        help_text="Date when the application window closes for this project.",
    )
    work_format = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Work format",
        help_text="Work format (remote / on-site / hybrid).",
    )
    credits = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Credits",
        help_text="Academic credits awarded for participation.",
    )
    hours_per_week = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Hours per week",
        help_text="Student load in hours per week.",
    )
    is_paid = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Is paid",
        help_text="Whether participation is paid.",
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Location",
        help_text="Implementation location.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        null=True,
        verbose_name="Created at",
        help_text="Timestamp when project was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        null=True,
        verbose_name="Updated at",
        help_text="Timestamp of the latest project update.",
    )

    objects = ProjectManager()

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"], name="projects_status_created_idx"),
            models.Index(fields=["owner", "created_at"], name="projects_owner_created_idx"),
        ]
        ordering = ["-created_at"]
        verbose_name = "Project"
        verbose_name_plural = "Projects"

    def __str__(self) -> str:
        return self.title

    def is_public(self) -> bool:
        return self.status in ProjectStatus.catalog_values()

    def get_tags_list(self) -> list[str]:
        if isinstance(self.tech_tags, list):
            return [str(tag) for tag in self.tech_tags]
        return []
