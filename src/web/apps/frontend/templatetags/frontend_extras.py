from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Return dictionary value by key, or None if missing."""
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)


@register.filter
def user_role(user):
    """Return user's role string ('student', 'customer', 'cpprp') or ''."""
    if not getattr(user, "is_authenticated", False):
        return ""
    try:
        return user.profile.role
    except Exception:
        return ""


@register.filter
def role_label(role):
    """Human-readable role label in Russian."""
    return {
        "student":  "Студент",
        "customer": "Заказчик",
        "cpprp":    "Модератор",
    }.get(role, role)
