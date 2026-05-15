from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):

    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)


@register.filter
def user_role(user):

    if not getattr(user, "is_authenticated", False):
        return ""
    try:
        return user.profile.role
    except Exception:
        return ""


@register.filter
def role_label(role):

    return {
        "student": "Студент",
        "customer": "Заказчик",
        "cpprp": "Модератор",
    }.get(role, role)
