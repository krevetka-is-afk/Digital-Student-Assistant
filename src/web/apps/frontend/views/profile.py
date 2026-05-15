from apps.applications.models import Application
from apps.frontend.forms import ProfileEditForm
from apps.frontend.utils import LOGIN_URL
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from apps.users.models import UserRole
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render


@login_required(login_url=LOGIN_URL)
def profile_view(request):
    user    = request.user
    profile = getattr(user, "profile", None)
    role    = profile.role if profile else ""

    if request.method == "POST":
        form = ProfileEditForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data["full_name"]
            bio       = form.cleaned_data["bio"]
            interests = form.cleaned_data["interests_raw"]

            parts = full_name.split(None, 1)
            user.first_name = parts[0] if parts else ""
            user.last_name  = parts[1] if len(parts) > 1 else ""
            with transaction.atomic():
                user.save(update_fields=["first_name", "last_name"])
                if profile:
                    profile.bio       = bio
                    profile.interests = interests
                    profile.save(update_fields=["bio", "interests"])

            messages.success(request, "Профиль обновлён.")
            return redirect("frontend:profile")
        interests_initial = request.POST.get("interests_raw", "")
    else:
        interests_initial = ",".join(profile.interests) if profile and profile.interests else ""
        form = ProfileEditForm(initial={
            "full_name":     f"{user.first_name} {user.last_name}".strip(),
            "bio":           profile.bio if profile else "",
            "interests_raw": interests_initial,
        })

    student_stats: dict = {}
    if role == UserRole.STUDENT and profile:
        student_stats = {
            "applications_count":        Application.objects.filter(applicant=user).count(),
            "bookmarks_count":           len(profile.favorite_project_ids or []),
            "initiative_projects_count": Project.objects.filter(
                owner=user,
                source_type=ProjectSourceType.INITIATIVE,
            ).count(),
        }

    moderation_queue_count = 0
    if role == UserRole.CPPRP:
        moderation_queue_count = Project.objects.filter(
            status=ProjectStatus.ON_MODERATION
        ).count()

    return render(request, "frontend/profile.html", {
        "profile_user":           user,
        "profile":                profile,
        "role":                   role,
        "form":                   form,
        "interests_initial":      interests_initial,
        "profile_errors":         {k: v[0] for k, v in form.errors.items()},
        "student_stats":          student_stats,
        "moderation_queue_count": moderation_queue_count,
    })
