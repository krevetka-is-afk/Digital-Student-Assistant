from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0008_add_supervisor_name"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Bookmark",
        ),
    ]
