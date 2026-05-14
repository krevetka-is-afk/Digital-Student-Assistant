from typing import cast

from apps.projects.models import Technology
from apps.projects.normalization import normalize_technology_tags
from django.conf import settings
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class UserRole(models.TextChoices):
    STUDENT = "student", "Student"
    CUSTOMER = "customer", "Customer"
    CPPRP = "cpprp", "CPPRP"


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="User",
        help_text="The Django user account linked to this profile.",
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
        db_index=True,
        verbose_name="Role",
        help_text="Temporary MVP role for access and filtering.",
    )
    bio = models.TextField(
        blank=True,
        default="",
        verbose_name="Bio",
        help_text="Short description about the user.",
    )
    interests = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Interests",
        help_text="Student interests used by search and recommendations.",
    )
    interest_technologies = models.ManyToManyField(
        Technology,
        blank=True,
        related_name="interested_profiles",
        verbose_name="Interest technologies",
        help_text="Canonical technology directory entries selected as student interests.",
    )
    favorite_project_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Favorite project ids",
        help_text="Project ids bookmarked by the user for the student catalog.",
    )
    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Email verified at",
        help_text="Timestamp when the user confirmed ownership of the email address.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Created at",
        help_text="Timestamp when profile was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated at",
        help_text="Timestamp of the latest profile update.",
    )

    class Meta:
        indexes = [
            models.Index(fields=["role", "created_at"], name="users_role_created_idx"),
        ]
        ordering = ["-created_at"]
        verbose_name = "User profile"
        verbose_name_plural = "User profiles"

    def __str__(self) -> str:
        return f"{self.user} ({self.role})"

    def save(self, *args, **kwargs):
        setattr(self, "interests", normalize_technology_tags(self.interests))
        setattr(
            self,
            "favorite_project_ids",
            self.normalize_favorite_project_ids(self.favorite_project_ids),
        )
        super().save(*args, **kwargs)
        self.sync_interest_technologies()

    def sync_interest_technologies(self) -> None:
        if not self.pk:
            return
        technologies = [
            Technology.objects.get_or_create_by_name(tag, created_by=self.user)[0]
            for tag in normalize_technology_tags(self.interests)
        ]
        getattr(self, "interest_technologies").set(technologies)

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified

    @staticmethod
    def normalize_favorite_project_ids(raw_value) -> list[int]:
        if raw_value is None:
            return []
        if not isinstance(raw_value, (list, tuple, set)):
            return []

        normalized: list[int] = []
        seen: set[int] = set()
        for raw_project_id in raw_value:
            try:
                project_id = int(raw_project_id)
            except (TypeError, ValueError):
                continue
            if project_id < 1 or project_id in seen:
                continue
            seen.add(project_id)
            normalized.append(project_id)
        return normalized

    def get_favorite_project_ids(self) -> list[int]:
        return self.normalize_favorite_project_ids(self.favorite_project_ids)

    def set_favorite_project_ids(self, project_ids: list[int]) -> None:
        setattr(self, "favorite_project_ids", self.normalize_favorite_project_ids(project_ids))

    def mark_email_verified(self, verified_at=None) -> None:
        self.email_verified_at = verified_at or timezone.now()


class EmailVerificationPurpose(models.TextChoices):
    SIGNUP = "signup", "Signup"


class EmailVerificationCode(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_verification_codes",
        verbose_name="User",
        help_text="The Django user account that requested verification.",
    )
    email = models.EmailField(
        db_index=True,
        verbose_name="Email",
        help_text="Email address that should be verified.",
    )
    purpose = models.CharField(
        max_length=20,
        choices=EmailVerificationPurpose.choices,
        default=EmailVerificationPurpose.SIGNUP,
        verbose_name="Purpose",
        help_text="Verification flow this code belongs to.",
    )
    code_hash = models.CharField(
        max_length=128,
        verbose_name="Code hash",
        help_text="Hashed verification code value.",
    )
    expires_at = models.DateTimeField(
        db_index=True,
        verbose_name="Expires at",
        help_text="Timestamp after which the code can no longer be used.",
    )
    sent_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Sent at",
        help_text="Timestamp when the verification code was issued.",
    )
    consumed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Consumed at",
        help_text="Timestamp when the code was successfully used or invalidated.",
    )
    attempt_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Attempt count",
        help_text="Number of failed verification attempts for this code.",
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "purpose", "consumed_at"],
                name="users_evc_user_purpose_idx",
            ),
            models.Index(
                fields=["email", "purpose"],
                name="users_evc_email_purpose_idx",
            ),
        ]
        ordering = ["-sent_at"]
        verbose_name = "Email verification code"
        verbose_name_plural = "Email verification codes"

    def __str__(self) -> str:
        return f"{self.email} ({self.purpose})"

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()


class ExternalAccessRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class ExternalAccessAllowlist(models.Model):
    email = models.EmailField(
        unique=True,
        db_index=True,
        verbose_name="Email",
        help_text="External email address allowed to register.",
    )
    allowed_role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        verbose_name="Allowed role",
        help_text="Role that can be used during registration for this email.",
    )
    note = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Note",
        help_text="Optional moderation note or source of approval.",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="approved_external_access_emails",
        null=True,
        blank=True,
        verbose_name="Approved by",
        help_text="Moderator who approved this external email.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Active",
        help_text="Whether this email is currently allowed to register.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["email"]
        verbose_name = "External access allowlist entry"
        verbose_name_plural = "External access allowlist"

    def __str__(self) -> str:
        return cast(str, self.email)

    def save(self, *args, **kwargs):
        setattr(self, "email", normalize_email(cast(str, self.email)))
        super().save(*args, **kwargs)


class ExternalAccessRequest(models.Model):
    email = models.EmailField(
        unique=True,
        db_index=True,
        verbose_name="Email",
        help_text="External email address requesting access.",
    )
    full_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Full name",
        help_text="Name provided during registration request.",
    )
    requested_role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        verbose_name="Requested role",
        help_text="Role requested by the external user.",
    )
    status = models.CharField(
        max_length=20,
        choices=ExternalAccessRequestStatus.choices,
        default=ExternalAccessRequestStatus.PENDING,
        db_index=True,
        verbose_name="Status",
        help_text="Current moderation status of the access request.",
    )
    decision_note = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Decision note",
        help_text="Optional moderation note.",
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="reviewed_external_access_requests",
        null=True,
        blank=True,
        verbose_name="Reviewed by",
        help_text="Moderator who made the latest decision.",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Reviewed at",
        help_text="Timestamp of the latest moderation decision.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "External access request"
        verbose_name_plural = "External access requests"

    def __str__(self) -> str:
        return cast(str, self.email)

    def save(self, *args, **kwargs):
        setattr(self, "email", normalize_email(cast(str, self.email)))
        super().save(*args, **kwargs)
