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

    def set_favorite_project_ids(self, project_ids: list[int]) -> None:
        normalized: list[int] = []
        seen: set[int] = set()
        for raw_project_id in project_ids:
            project_id = int(raw_project_id)
            if project_id in seen:
                continue
            seen.add(project_id)
            normalized.append(project_id)
        setattr(self, "favorite_project_ids", normalized)

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
