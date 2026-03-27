from datetime import date

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
    STAFFED = "staffed", "Staffed"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"
    REJECTED = "rejected", "Rejected"
    ARCHIVED = "archived", "Archived"

    @classmethod
    def catalog_values(cls) -> tuple[str, ...]:
        return (cls.PUBLISHED, cls.STAFFED)


class ProjectSourceType(models.TextChoices):
    SUPERVISOR = "supervisor", "Supervisor"
    INITIATIVE = "initiative", "Initiative"
    EPP = "epp", "EPP"
    MANUAL = "manual", "Manual"


class EPP(models.Model):
    source_ref = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Source reference",
        help_text="Unique EPP identifier from the source file.",
    )
    title = models.TextField(
        blank=True,
        verbose_name="Title",
        help_text="EPP title from the source file.",
    )
    campaign_ref = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Campaign reference",
        help_text="Campaign identifier from the source file.",
    )
    campaign_title = models.TextField(
        blank=True,
        verbose_name="Campaign title",
        help_text="Campaign title from the source file.",
    )
    created_at_source = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Created at source",
        help_text="Creation timestamp from the source file.",
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Start date",
        help_text="Start date from the source file.",
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="End date",
        help_text="End date from the source file.",
    )
    supervisor_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Supervisor name",
        help_text="EPP supervisor name from the source file.",
    )
    supervisor_email = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Supervisor email",
        help_text="EPP supervisor email from the source file.",
    )
    supervisor_department = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Supervisor department",
        help_text="Supervisor department from the source file.",
    )
    initiator_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Initiator name",
        help_text="EPP initiator from the source file.",
    )
    initiator_type = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Initiator type",
        help_text="EPP initiator type from the source file.",
    )
    status_raw = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Source status",
        help_text="Raw EPP status from the source file.",
    )
    raw_payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Raw payload",
        help_text="Complete EPP source payload for round-trip compatibility.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Created at",
        help_text="Timestamp when EPP record was created locally.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated at",
        help_text="Timestamp of the latest local EPP update.",
    )

    class Meta:
        ordering = ["source_ref"]
        verbose_name = "EPP"
        verbose_name_plural = "EPP records"

    def __str__(self) -> str:
        return f"EPP {self.source_ref}"


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
        help_text="App-facing vacancy title shown in catalog and API lists.",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="App-facing project description built from source fields when available.",
    )
    tech_tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Tech tags",
        help_text="Normalized technology tags derived from source fields.",
    )
    epp = models.ForeignKey(
        EPP,
        on_delete=models.CASCADE,
        related_name="projects",
        null=True,
        blank=True,
        verbose_name="EPP",
        help_text="Parent EPP record for file-native vacancy imports.",
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="owned_projects",
        null=True,
        verbose_name="Owner",
        help_text="Project owner (mentor/customer) who created or owns this project.",
    )
    status = models.CharField(
        max_length=32,
        choices=ProjectStatus.choices,
        default=ProjectStatus.DRAFT,
        db_index=True,
        verbose_name="Status",
        help_text="Normalized publishing lifecycle state used in filters and workflows.",
    )
    team_size = models.PositiveIntegerField(
        default=1,
        verbose_name="Team size",
        help_text="Number of students needed for this project.",
    )
    study_course = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Study course",
        help_text="Recommended course for applicants when known.",
    )
    education_program = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Education program",
        help_text="Recommended education program or OP for applicants.",
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
        help_text="External source identifier for the vacancy/topic row.",
    )
    source_row_index = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Source row index",
        help_text="1-based row number from the original spreadsheet.",
    )
    vacancy_title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Vacancy title",
        help_text="Source vacancy title.",
    )
    vacancy_title_en = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Vacancy title in English",
        help_text="Source vacancy title in English.",
    )
    thesis_title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Thesis title",
        help_text="Source thesis title.",
    )
    thesis_title_en = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Thesis title in English",
        help_text="Source thesis title in English.",
    )
    implementation_language = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Implementation language",
        help_text="Source implementation language.",
    )
    activity_type = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Activity type",
        help_text="Source activity type.",
    )
    supervisor_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Supervisor name",
        help_text="Supervisor name for the vacancy/topic.",
    )
    supervisor_email = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Supervisor email",
        help_text="Supervisor email for the vacancy/topic.",
    )
    supervisor_department = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Supervisor department",
        help_text="Supervisor department for the vacancy/topic.",
    )
    supervisor_staff_category = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Supervisor staff category",
        help_text="Supervisor staff category from the source file.",
    )
    co_supervisors = models.TextField(
        blank=True,
        verbose_name="Co-supervisors",
        help_text="Co-supervisors for the vacancy/topic.",
    )
    startup_as_thesis = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Startup as thesis",
        help_text='Whether "Startup as thesis" is enabled in source data.',
    )
    applications_count_source = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Applications count in source",
        help_text="Current applications count from source data.",
    )
    credits = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Credits",
        help_text="Credits from source data.",
    )
    hours_per_week = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Hours per week",
        help_text="Student load in hours per week from source data.",
    )
    control_form = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Control form",
        help_text="Control form from source data.",
    )
    work_format = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Work format",
        help_text="Work format from source data.",
    )
    application_opened_at = models.DateField(
        null=True,
        blank=True,
        verbose_name="Applications open at",
        help_text="Date when the application window opens for this project.",
    )
    application_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="Application deadline",
        help_text="Date when the application window closes for this project.",
    )
    student_participation_format = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Student participation format",
        help_text="Student participation format from source data.",
    )
    results_presentation_format = models.TextField(
        blank=True,
        verbose_name="Results presentation format",
        help_text="Results presentation and defense format from source data.",
    )
    grading_formula = models.TextField(
        blank=True,
        verbose_name="Grading formula",
        help_text="Grading formula from source data.",
    )
    implementation_features = models.TextField(
        blank=True,
        verbose_name="Implementation features",
        help_text="Implementation features from source data.",
    )
    selection_criteria = models.TextField(
        blank=True,
        verbose_name="Selection criteria",
        help_text="Selection criteria from source data.",
    )
    is_paid = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Is paid",
        help_text="Whether participation is paid.",
    )
    retakes_allowed = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Retakes allowed",
        help_text="Whether retakes are allowed.",
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Location",
        help_text="Implementation location from source data.",
    )
    internal_customer = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Internal customer",
        help_text="Internal customer from source data.",
    )
    external_customer_location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="External customer location",
        help_text="Location of external organization from source data.",
    )
    external_customer = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="External customer",
        help_text="External customer from source data.",
    )
    inn = models.CharField(
        max_length=32,
        blank=True,
        verbose_name="INN",
        help_text="INN from source data.",
    )
    organization_type = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Organization type",
        help_text="Organization type from source data.",
    )
    cooperation_type = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Cooperation type",
        help_text="Cooperation type from source data.",
    )
    practice_contract_status = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Practice contract status",
        help_text="Status of practice contract from source data.",
    )
    contract_number = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Contract number",
        help_text="Contract number from source data.",
    )
    contract_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Contract date",
        help_text="Contract date from source data.",
    )
    uses_ai = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Uses AI",
        help_text="Whether AI is planned in the work.",
    )
    digital_tools = models.TextField(
        blank=True,
        verbose_name="Digital tools",
        help_text="Digital tools from source data.",
    )
    usage_areas = models.TextField(
        blank=True,
        verbose_name="Usage areas",
        help_text="Usage areas from source data.",
    )
    python_libraries = models.TextField(
        blank=True,
        verbose_name="Python libraries",
        help_text="Python libraries from source data.",
    )
    methods = models.TextField(
        blank=True,
        verbose_name="Methods",
        help_text="Methods from source data.",
    )
    programming_languages = models.TextField(
        blank=True,
        verbose_name="Programming languages",
        help_text="Programming languages from source data.",
    )
    data_tools = models.TextField(
        blank=True,
        verbose_name="Data tools",
        help_text="Data tools and methods from source data.",
    )
    vacancy_initiator = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Vacancy initiator",
        help_text="Vacancy initiator from source data.",
    )
    vacancy_initiator_type = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Vacancy initiator type",
        help_text="Vacancy initiator type from source data.",
    )
    vacancy_tags = models.TextField(
        blank=True,
        verbose_name="Vacancy tags",
        help_text="Vacancy tags from source data.",
    )
    status_raw = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Source status",
        help_text="Raw vacancy status from the source file.",
    )
    raw_payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Raw payload",
        help_text="Complete vacancy source payload for round-trip compatibility.",
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
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_ref"],
                name="projects_unique_source_type_ref",
                condition=~Q(source_ref=""),
            )
        ]
        indexes = [
            models.Index(fields=["status", "created_at"], name="projects_status_created_idx"),
            models.Index(fields=["owner", "created_at"], name="projects_owner_created_idx"),
            models.Index(fields=["epp", "status"], name="projects_epp_status_idx"),
            models.Index(fields=["owner", "status"], name="projects_owner_status_idx"),
            models.Index(fields=["supervisor_email"], name="projects_supervisor_email_idx"),
        ]
        ordering = ["-created_at"]
        verbose_name = "Project"
        verbose_name_plural = "Projects"

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if self.vacancy_title and not self.title:
            self.title = self.vacancy_title
        elif self.title and not self.vacancy_title:
            self.vacancy_title = self.title

        if not self.description:
            self.description = self.build_source_description()

        if not self.tech_tags:
            self.tech_tags = self.build_tech_tags()

        super().save(*args, **kwargs)

    def build_source_description(self) -> str:
        parts = [
            self.implementation_features.strip(),
            self.selection_criteria.strip(),
            self.work_format.strip(),
            self.student_participation_format.strip(),
        ]
        return "\n\n".join(part for part in parts if part)

    def build_tech_tags(self) -> list[str]:
        items: list[str] = []
        for raw_value in (
            self.python_libraries,
            self.methods,
            self.programming_languages,
            self.data_tools,
            self.vacancy_tags,
        ):
            if not raw_value:
                continue
            pieces = [item.strip() for item in str(raw_value).replace(";", ",").split(",")]
            items.extend(piece for piece in pieces if piece)
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            marker = item.lower()
            if marker in seen:
                continue
            seen.add(marker)
            deduped.append(item)
        return deduped

    def is_public(self) -> bool:
        return self.status in ProjectStatus.catalog_values()

    def get_tags_list(self) -> list[str]:
        if isinstance(self.tech_tags, list):
            return [str(tag) for tag in self.tech_tags]
        return []

    @property
    def is_team_project(self) -> bool:
        return self.team_size > 1

    @property
    def staffing_state(self) -> str:
        if self.accepted_participants_count >= self.team_size:
            return "full"
        return "open"

    @property
    def application_window_state(self) -> str:
        today = date.today()
        if self.application_opened_at and today < self.application_opened_at:
            return "upcoming"
        if self.application_deadline and today > self.application_deadline:
            return "closed"
        return "open"
