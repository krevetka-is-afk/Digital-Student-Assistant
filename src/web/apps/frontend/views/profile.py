from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.applications.models import Application
from apps.projects.models import Project, ProjectStatus
from apps.users.models import UserRole


@login_required(login_url="/auth/")
def profile_view(request):
    """Logged-in user's profile page — view and edit."""
    user = request.user
    try:
        profile = user.profile
        role    = profile.role
    except Exception:
        profile = None
        role    = ""

    profile_errors = {}

    if request.method == "POST":
        full_name     = request.POST.get("full_name", "").strip()
        bio           = request.POST.get("bio", "").strip()
        interests_raw = request.POST.get("interests_raw", "").strip()

        parts      = full_name.split(None, 1)
        first_name = parts[0] if parts else ""
        last_name  = parts[1] if len(parts) > 1 else ""

        user.first_name = first_name
        user.last_name  = last_name
        user.save(update_fields=["first_name", "last_name"])

        if profile:
            profile.bio = bio
            if interests_raw:
                profile.interests = [t.strip() for t in interests_raw.split(",") if t.strip()]
            else:
                profile.interests = []
            profile.save(update_fields=["bio", "interests"])

        messages.success(request, "Профиль обновлён.")
        return redirect("frontend:profile")

    own_projects_count = 0
    if role == UserRole.CUSTOMER:
        own_projects_count = Project.objects.filter(owner=user).count()

    applications_count = 0
    if role == UserRole.STUDENT:
        applications_count = Application.objects.filter(applicant=user).count()

    moderation_queue_count = 0
    if role == UserRole.CPPRP:
        moderation_queue_count = Project.objects.filter(status=ProjectStatus.ON_MODERATION).count()

    interests_initial = ",".join(profile.interests) if profile and profile.interests else ""

    context = {
        "profile_user":           user,
        "profile":                profile,
        "role":                   role,
        "own_projects_count":     own_projects_count,
        "applications_count":     applications_count,
        "moderation_queue_count": moderation_queue_count,
        "interests_initial":      interests_initial,
        "profile_errors":         profile_errors,
    }
    return render(request, "frontend/profile.html", context)
