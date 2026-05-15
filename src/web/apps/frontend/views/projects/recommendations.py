from apps.frontend.utils import LOGIN_URL
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse


@login_required(login_url=LOGIN_URL)
def recommendations_view(request):
    return redirect(reverse("frontend:project_list") + "?tab=recs")
