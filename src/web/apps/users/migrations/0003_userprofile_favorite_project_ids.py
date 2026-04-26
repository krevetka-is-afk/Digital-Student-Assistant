from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_userprofile_bio"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="favorite_project_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Project ids bookmarked by the user for the student catalog.",
                verbose_name="Favorite project ids",
            ),
        ),
    ]
