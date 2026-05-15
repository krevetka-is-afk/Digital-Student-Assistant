from apps.frontend.utils import LOGIN_URL
from apps.projects.models import Project
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST


@require_POST
@login_required(login_url=LOGIN_URL)
def toggle_bookmark(request, pk):
    get_object_or_404(Project, pk=pk)
    profile   = request.user.profile
    favorites = list(profile.favorite_project_ids)

    if pk in favorites:
        favorites.remove(pk)
        bookmarked = False
    else:
        favorites.append(pk)
        bookmarked = True

    profile.set_favorite_project_ids(favorites)
    profile.save(update_fields=["favorite_project_ids"])
    return JsonResponse({"bookmarked": bookmarked})
