import re

from django.db import migrations

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


def normalize_profile_interests(apps, schema_editor):
    UserProfile = apps.get_model("users", "UserProfile")
    for profile in UserProfile.objects.only("id", "interests").iterator():
        normalized_interests = _normalize_interests(profile.interests)
        if normalized_interests != profile.interests:
            profile.interests = normalized_interests
            profile.save(update_fields=["interests"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_email_verification"),
    ]

    operations = [
        migrations.RunPython(normalize_profile_interests, migrations.RunPython.noop),
    ]
