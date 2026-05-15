from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0006_userprofile_interest_technologies"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalAccessAllowlist",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        db_index=True,
                        help_text="External email address allowed to register.",
                        max_length=254,
                        unique=True,
                        verbose_name="Email",
                    ),
                ),
                (
                    "allowed_role",
                    models.CharField(
                        choices=[
                            ("student", "Student"),
                            ("customer", "Customer"),
                            ("cpprp", "CPPRP"),
                        ],
                        default="customer",
                        help_text="Role that can be used during registration for this email.",
                        max_length=20,
                        verbose_name="Allowed role",
                    ),
                ),
                (
                    "note",
                    models.CharField(
                        blank=True,
                        help_text="Optional moderation note or source of approval.",
                        max_length=255,
                        verbose_name="Note",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        help_text="Whether this email is currently allowed to register.",
                        verbose_name="Active",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="Moderator who approved this external email.",
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="approved_external_access_emails",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Approved by",
                    ),
                ),
            ],
            options={
                "verbose_name": "External access allowlist entry",
                "verbose_name_plural": "External access allowlist",
                "ordering": ["email"],
            },
        ),
        migrations.CreateModel(
            name="ExternalAccessRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        db_index=True,
                        help_text="External email address requesting access.",
                        max_length=254,
                        unique=True,
                        verbose_name="Email",
                    ),
                ),
                (
                    "full_name",
                    models.CharField(
                        blank=True,
                        help_text="Name provided during registration request.",
                        max_length=255,
                        verbose_name="Full name",
                    ),
                ),
                (
                    "requested_role",
                    models.CharField(
                        choices=[
                            ("student", "Student"),
                            ("customer", "Customer"),
                            ("cpprp", "CPPRP"),
                        ],
                        default="customer",
                        help_text="Role requested by the external user.",
                        max_length=20,
                        verbose_name="Requested role",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="pending",
                        help_text="Current moderation status of the access request.",
                        max_length=20,
                        verbose_name="Status",
                    ),
                ),
                (
                    "decision_note",
                    models.CharField(
                        blank=True,
                        help_text="Optional moderation note.",
                        max_length=255,
                        verbose_name="Decision note",
                    ),
                ),
                (
                    "reviewed_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Timestamp of the latest moderation decision.",
                        null=True,
                        verbose_name="Reviewed at",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="Moderator who made the latest decision.",
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="reviewed_external_access_requests",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Reviewed by",
                    ),
                ),
            ],
            options={
                "verbose_name": "External access request",
                "verbose_name_plural": "External access requests",
                "ordering": ["-created_at"],
            },
        ),
    ]
