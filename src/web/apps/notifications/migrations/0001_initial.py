import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(db_index=True, max_length=120)),
                ("title", models.CharField(max_length=255)),
                ("body", models.TextField(blank=True, default="")),
                ("target_type", models.CharField(db_index=True, max_length=50)),
                ("target_id", models.CharField(db_index=True, max_length=100)),
                ("dedupe_key", models.CharField(blank=True, help_text="Optional idempotency key to avoid duplicates for retried actions.", max_length=255, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("read_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("email_status", models.CharField(choices=[("skipped", "Skipped"), ("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")], db_index=True, default="pending", max_length=20)),
                ("email_sent_at", models.DateTimeField(blank=True, null=True)),
                ("email_error", models.TextField(blank=True, default="")),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications_acted", to=settings.AUTH_USER_MODEL)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["recipient", "created_at"], name="notif_recipient_time_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["recipient", "read_at"], name="notif_recipient_read_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["target_type", "target_id"], name="notif_target_idx"),
        ),
    ]
