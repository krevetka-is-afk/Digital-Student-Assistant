from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0013_technology_directory"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="academic_year",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text='Academic year this project belongs to, e.g. "2024-2025".',
                max_length=9,
                verbose_name="Academic year",
            ),
        ),
    ]
