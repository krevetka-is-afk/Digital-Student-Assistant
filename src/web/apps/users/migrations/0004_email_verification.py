import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F


def mark_existing_users_verified(apps, schema_editor):
    UserProfile = apps.get_model("users", "UserProfile")
    UserProfile.objects.filter(
        user__is_active=True,
        email_verified_at__isnull=True,
    ).update(email_verified_at=F("created_at"))


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_merge_userprofile_bio_and_favorites"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="email_verified_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Timestamp when the user confirmed ownership of the email address.",
                null=True,
                verbose_name="Email verified at",
            ),
        ),
        migrations.CreateModel(
            name="EmailVerificationCode",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        db_index=True,
                        help_text="Email address that should be verified.",
                        max_length=254,
                        verbose_name="Email",
                    ),
                ),
                (
                    "purpose",
                    models.CharField(
                        choices=[("signup", "Signup")],
                        default="signup",
                        help_text="Verification flow this code belongs to.",
                        max_length=20,
                        verbose_name="Purpose",
                    ),
                ),
                (
                    "code_hash",
                    models.CharField(
                        help_text="Hashed verification code value.",
                        max_length=128,
                        verbose_name="Code hash",
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        db_index=True,
                        help_text="Timestamp after which the code can no longer be used.",
                        verbose_name="Expires at",
                    ),
                ),
                (
                    "sent_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        help_text="Timestamp when the verification code was issued.",
                        verbose_name="Sent at",
                    ),
                ),
                (
                    "consumed_at",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        help_text="Timestamp when the code was successfully used or invalidated.",
                        null=True,
                        verbose_name="Consumed at",
                    ),
                ),
                (
                    "attempt_count",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Number of failed verification attempts for this code.",
                        verbose_name="Attempt count",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="The Django user account that requested verification.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_verification_codes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="User",
                    ),
                ),
            ],
            options={
                "verbose_name": "Email verification code",
                "verbose_name_plural": "Email verification codes",
                "ordering": ["-sent_at"],
                "indexes": [
                    models.Index(
                        fields=["user", "purpose", "consumed_at"],
                        name="users_evc_user_purpose_idx",
                    ),
                    models.Index(
                        fields=["email", "purpose"],
                        name="users_evc_email_purpose_idx",
                    ),
                ],
            },
        ),
        migrations.RunPython(mark_existing_users_verified, migrations.RunPython.noop),
    ]
