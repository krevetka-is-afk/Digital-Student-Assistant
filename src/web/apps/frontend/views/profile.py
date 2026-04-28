from apps.applications.models import Application
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from apps.projects.normalization import normalize_technology_tags
from apps.users.models import UserRole
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

# Field length limits
_NAME_MAX = 100
_BIO_MAX = 500
_INTERESTS_MAX = 20
_INTEREST_ITEM_MAX = 100


def _parse_interests(raw: str) -> list[str]:
    """Split comma-separated interests and normalize them to technology tag shape."""
    return normalize_technology_tags(raw.split(","))


@login_required(login_url="/auth/")
def profile_view(request):
    """Logged-in user's profile page — view and edit."""
    user = request.user
    try:
        profile = user.profile
        role = profile.role
    except Exception:
        profile = None
        role = ""

    profile_errors: dict[str, str] = {}

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        bio = request.POST.get("bio", "").strip()
        interests_raw = request.POST.get("interests_raw", "").strip()

        # --- Validate ---
        if len(full_name) > _NAME_MAX:
            profile_errors["full_name"] = f"Имя не может превышать {_NAME_MAX} символов."
        if len(bio) > _BIO_MAX:
            profile_errors["bio"] = f"Описание не может превышать {_BIO_MAX} символов."

        raw_interests = _parse_interests(interests_raw)
        too_long_interests = [t for t in raw_interests if len(t) > _INTEREST_ITEM_MAX]
        if too_long_interests:
            profile_errors["interests"] = (
                f"Каждый интерес не может превышать {_INTEREST_ITEM_MAX} символов."
            )
        elif len(raw_interests) > _INTERESTS_MAX:
            profile_errors["interests"] = f"Максимум {_INTERESTS_MAX} интересов."

        if profile_errors:
            # Re-render with errors — fall through to context below
            pass
        else:
            parts = full_name.split(None, 1)
            first_name = parts[0] if parts else ""
            last_name = parts[1] if len(parts) > 1 else ""

            user.first_name = first_name
            user.last_name = last_name
            user.save(update_fields=["first_name", "last_name"])

            if profile:
                profile.bio = bio
                profile.interests = raw_interests
                profile.save(update_fields=["bio", "interests"])

            messages.success(request, "Профиль обновлён.")
            return redirect("frontend:profile")

    own_projects_count = 0
    if role == UserRole.CUSTOMER:
        own_projects_count = Project.objects.filter(owner=user).count()

    applications_count = 0
    bookmarks_count = 0
    initiative_count = 0
    if role == UserRole.STUDENT:
        applications_count = Application.objects.filter(applicant=user).count()
        bookmarks_count = len(profile.favorite_project_ids) if profile else 0
        initiative_count = Project.objects.filter(
            owner=user, source_type=ProjectSourceType.INITIATIVE
        ).count()

    moderation_queue_count = 0
    if role == UserRole.CPPRP:
        moderation_queue_count = Project.objects.filter(status=ProjectStatus.ON_MODERATION).count()

    if profile_errors and request.method == "POST":
        # On validation failure preserve what the user typed
        interests_initial = request.POST.get("interests_raw", "")
    else:
        interests_initial = ",".join(profile.interests) if profile and profile.interests else ""

    context = {
        "profile_user": user,
        "profile": profile,
        "role": role,
        "own_projects_count": own_projects_count,
        "applications_count": applications_count,
        "bookmarks_count": bookmarks_count,
        "initiative_count": initiative_count,
        "moderation_queue_count": moderation_queue_count,
        "interests_initial": interests_initial,
        "profile_errors": profile_errors,
    }
    return render(request, "frontend/profile.html", context)
