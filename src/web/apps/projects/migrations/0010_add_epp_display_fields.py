from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0009_remove_bookmark"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="study_course",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name="Study course",
                help_text="Recommended course for applicants when known.",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="education_program",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Education program",
                help_text="Recommended education program or OP for applicants.",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="application_deadline",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Application deadline",
                help_text="Date when the application window closes for this project.",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="work_format",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Work format",
                help_text="Work format (remote / on-site / hybrid).",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="credits",
            field=models.DecimalField(
                blank=True,
                null=True,
                max_digits=8,
                decimal_places=2,
                verbose_name="Credits",
                help_text="Academic credits awarded for participation.",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="hours_per_week",
            field=models.DecimalField(
                blank=True,
                null=True,
                max_digits=8,
                decimal_places=2,
                verbose_name="Hours per week",
                help_text="Student load in hours per week.",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="is_paid",
            field=models.BooleanField(
                blank=True,
                null=True,
                verbose_name="Is paid",
                help_text="Whether participation is paid.",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="location",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Location",
                help_text="Implementation location.",
            ),
        ),
    ]
