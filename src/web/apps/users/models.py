from django.conf import settings
from django.db import models

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
    interests = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Interests",
        help_text="Student interests used by search and recommendations.",
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
