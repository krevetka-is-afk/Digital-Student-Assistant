import json

from apps.account.permissions import has_any_role
from apps.applications.models import Application, ApplicationStatus
from apps.projects.models import ProjectStatus
from apps.users.models import UserRole
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse


def _require_student(request) -> HttpResponse | None:

    if not has_any_role(request.user, allowed={UserRole.STUDENT}, allow_staff=False):
        response = HttpResponse(status=403)
        response["HX-Trigger"] = _toast_trigger("Подавать заявки могут только студенты.", "error")
        return response
    return None

def _htmx_unauth_response(request, pk: int) -> HttpResponse:
    if request.headers.get("HX-Request"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = (
            reverse("frontend:auth")
            + f"?next={reverse('frontend:project_detail', kwargs={'pk': pk})}"
        )
        return response
    return JsonResponse(
        {"error": "unauthenticated", "redirect": reverse("frontend:auth")},
        status=401,
    )

def _toast_trigger(message: str, toast_type: str = "info") -> str:
    return json.dumps({"showToast": {"message": message, "type": toast_type}})

def _build_apply_response(request, source: str, project, application) -> HttpResponse:
    if source == "card":
        return render(request, "frontend/partials/apply_button.html", {
            "project":            project,
            "application_status": application.status,
            "ApplicationStatus":  ApplicationStatus,
            "ProjectStatus":      ProjectStatus,
        })
    return render(request, "frontend/partials/apply_action_detail.html", {
        "project":           project,
        "application":       application,
        "is_owner":          False,
        "ApplicationStatus": ApplicationStatus,
        "ProjectStatus":     ProjectStatus,
    })

class OwnedSubmittedApplicationMixin:
    status_error_message: str = "Действие доступно только для заявки со статусом «На рассмотрении»."

    def dispatch(self, request, *args, **kwargs):
        application = get_object_or_404(
            Application.objects.select_related("project"),
            pk=kwargs["pk"],
        )
        if application.applicant != request.user:
            raise PermissionDenied
        if application.status != ApplicationStatus.SUBMITTED:
            messages.error(request, self.status_error_message)
            return redirect("frontend:project_list")
        self.application = application
        return super().dispatch(request, *args, **kwargs)
