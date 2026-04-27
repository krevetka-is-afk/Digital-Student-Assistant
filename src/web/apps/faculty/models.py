from __future__ import annotations

from django.db import models


class FacultyMatchStatus(models.TextChoices):
    CANDIDATE = "candidate", "Candidate"
    CONFIRMED = "confirmed", "Confirmed"
    REJECTED = "rejected", "Rejected"
    AMBIGUOUS = "ambiguous", "Ambiguous"
    UNMATCHED = "unmatched", "Unmatched"


class FacultyPerson(models.Model):
    source_person_id = models.CharField(max_length=100, blank=True, db_index=True)
    source_profile_url = models.URLField(max_length=500, unique=True)
    source_key = models.CharField(max_length=255, unique=True)
    full_name = models.CharField(max_length=255)
    full_name_normalized = models.CharField(max_length=255, db_index=True)
    primary_unit = models.CharField(max_length=255, blank=True)
    primary_unit_normalized = models.CharField(max_length=255, blank=True, db_index=True)
    campus_id = models.CharField(max_length=100, blank=True)
    campus_name = models.CharField(max_length=255, blank=True)
    publications_total = models.PositiveIntegerField(default=0)
    emails = models.JSONField(default=list, blank=True)
    interests = models.JSONField(default=list, blank=True)
    languages = models.JSONField(default=list, blank=True)
    positions = models.JSONField(default=list, blank=True)
    relations = models.JSONField(default=dict, blank=True)
    research_ids = models.JSONField(default=dict, blank=True)
    public_payload = models.JSONField(default=dict, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    source_hash = models.CharField(max_length=64, db_index=True)
    source_seen_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)
    is_stale = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name", "source_key"]
        indexes = [
            models.Index(fields=["full_name_normalized", "primary_unit_normalized"]),
            models.Index(fields=["is_stale", "updated_at"]),
        ]

    def __str__(self) -> str:
        return self.full_name


class FacultyPublication(models.Model):
    source_publication_id = models.CharField(max_length=255, unique=True)
    title = models.TextField()
    publication_type = models.CharField(max_length=100, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    language = models.CharField(max_length=100, blank=True)
    url = models.URLField(max_length=500, blank=True)
    created_at_source = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    source_hash = models.CharField(max_length=64, db_index=True)
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "title"]

    def __str__(self) -> str:
        return self.title


class FacultyAuthorship(models.Model):
    publication = models.ForeignKey(
        FacultyPublication,
        on_delete=models.CASCADE,
        related_name="authorships",
    )
    person = models.ForeignKey(
        FacultyPerson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authorships",
    )
    position = models.PositiveIntegerField()
    display_name = models.CharField(max_length=255)
    href = models.URLField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["publication", "position"],
                name="faculty_unique_authorship_position",
            )
        ]
        ordering = ["publication_id", "position"]


class FacultyCourse(models.Model):
    person = models.ForeignKey(FacultyPerson, on_delete=models.CASCADE, related_name="courses")
    course_key = models.CharField(max_length=255, unique=True)
    title = models.TextField()
    url = models.URLField(max_length=500, blank=True)
    academic_year = models.CharField(max_length=50, blank=True)
    language = models.CharField(max_length=100, blank=True)
    level = models.CharField(max_length=100, blank=True)
    raw_meta = models.TextField(blank=True)
    source_hash = models.CharField(max_length=64, db_index=True)
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["person_id", "-academic_year", "title"]

    def __str__(self) -> str:
        return self.title


class FacultySyncState(models.Model):
    resource = models.CharField(max_length=100, unique=True)
    cursor = models.CharField(max_length=255, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    stats = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["resource"]

    def __str__(self) -> str:
        return self.resource


class ProjectFacultyMatch(models.Model):
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="faculty_matches",
    )
    faculty_person = models.ForeignKey(
        FacultyPerson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_matches",
    )
    supervisor_name = models.CharField(max_length=255, blank=True)
    supervisor_email = models.CharField(max_length=255, blank=True)
    supervisor_department = models.CharField(max_length=255, blank=True)
    match_strategy = models.CharField(max_length=100, blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=FacultyMatchStatus.choices,
        default=FacultyMatchStatus.CANDIDATE,
        db_index=True,
    )
    candidate_person_ids = models.JSONField(default=list, blank=True)
    matched_by = models.CharField(max_length=100, default="system", blank=True)
    matched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project"], name="faculty_unique_project_match")
        ]
        ordering = ["project_id"]

    def __str__(self) -> str:
        return f"Project {self.project_id}: {self.status}"
