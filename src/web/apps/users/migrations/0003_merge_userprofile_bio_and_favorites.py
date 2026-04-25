from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0002_userprofile_bio"),
        ("users", "0002_userprofile_favorite_project_ids"),
    ]

    operations = []
