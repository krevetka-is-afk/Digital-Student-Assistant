import re

from django.db import migrations, models

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_interests(values):
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []

    normalized = []
    seen = set()
    for raw_value in values:
        interest = _WHITESPACE_RE.sub(" ", str(raw_value).strip().lower())
        if not interest or interest in seen:
            continue
        seen.add(interest)
        normalized.append(interest)
    return normalized


def _get_or_create_technology(Technology, interest, *, created_by_id=None):
    normalized = _WHITESPACE_RE.sub(" ", str(interest).strip().lower())
    technology, _ = Technology.objects.get_or_create(
        normalized_name=normalized,
        defaults={
            "name": normalized,
            "status": "pending",
            "created_by_id": created_by_id,
        },
    )
    return technology


def populate_interest_technologies(apps, schema_editor):
    UserProfile = apps.get_model("users", "UserProfile")
    Technology = apps.get_model("projects", "Technology")
    for profile in UserProfile.objects.only("id", "user_id", "interests").iterator():
        technologies = [
            _get_or_create_technology(Technology, interest, created_by_id=profile.user_id)
            for interest in _normalize_interests(profile.interests)
        ]
        profile.interest_technologies.set(technologies)


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0013_technology_directory"),
        ("users", "0005_normalize_profile_interests"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="interest_technologies",
            field=models.ManyToManyField(
                blank=True,
                help_text="Canonical technology directory entries selected as student interests.",
                related_name="interested_profiles",
                to="projects.technology",
                verbose_name="Interest technologies",
            ),
        ),
        migrations.RunPython(populate_interest_technologies, migrations.RunPython.noop),
    ]
