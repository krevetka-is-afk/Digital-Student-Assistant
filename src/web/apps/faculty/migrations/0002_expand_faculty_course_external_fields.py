from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("faculty", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="facultycourse",
            name="url",
            field=models.URLField(blank=True, max_length=1000),
        ),
        migrations.AlterField(
            model_name="facultycourse",
            name="language",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="facultycourse",
            name="level",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="facultycourse",
            name="raw_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
