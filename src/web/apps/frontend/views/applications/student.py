from apps.applications.services import create_application, delete_application, update_motivation
from apps.frontend.forms import MotivationForm
from apps.frontend.utils import LOGIN_URL
from apps.projects.models import Project
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from rest_framework.exceptions import ValidationError as DRFValidationError

from .mixins import (
    OwnedSubmittedApplicationMixin,
    _build_apply_response,
    _htmx_unauth_response,
    _require_student,
    _toast_trigger,
)


@require_POST
def submit_application(request, pk):
    if not request.user.is_authenticated:
        return _htmx_unauth_response(request, pk)
    if err := _require_student(request):
        return err

    project = get_object_or_404(Project, pk=pk)

    form = MotivationForm(request.POST)
    if not form.is_valid():
        error_msg = next(iter(form.errors.values()))[0]
        response = HttpResponse(status=422)
        response["HX-Trigger"] = _toast_trigger(error_msg, "error")
        return response

    try:
        application, created = create_application(
            project=project,
            applicant=request.user,
            motivation=form.cleaned_data["motivation"],
        )
    except DRFValidationError:
        response = HttpResponse(status=422)
        response["HX-Trigger"] = _toast_trigger(
            "Проект в данный момент не принимает заявки.", "error"
        )
        return response

    toast_msg = (
        "Заявка успешно отправлена!" if created else "Вы уже подавали заявку на этот проект."
    )
    toast_type = "success" if created else "info"

    response = _build_apply_response(
        request, request.POST.get("source", "detail"), project, application
    )
    response["HX-Trigger"] = _toast_trigger(toast_msg, toast_type)
    return response


@method_decorator(require_POST, name="dispatch")
class WithdrawApplicationView(LoginRequiredMixin, OwnedSubmittedApplicationMixin, View):
    login_url = LOGIN_URL
    status_error_message = "Отозвать можно только заявку со статусом «На рассмотрении»."

    def post(self, request, pk):
        project_title = self.application.project.title
        delete_application(self.application)
        messages.success(request, f"Заявка на проект «{project_title}» отозвана.")
        return redirect("frontend:project_list")


class EditApplicationView(LoginRequiredMixin, OwnedSubmittedApplicationMixin, View):
    login_url = LOGIN_URL
    template_name = "frontend/edit_application.html"
    status_error_message = "Редактировать можно только заявку со статусом «На рассмотрении»."

    def get(self, request, pk):
        form = MotivationForm(initial={"motivation": self.application.motivation})
        return render(request, self.template_name, self._build_context(form=form))

    def post(self, request, pk):
        form = MotivationForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._build_context(form=form))
        update_motivation(self.application, form.cleaned_data["motivation"])
        messages.success(request, "Мотивация обновлена.")
        return redirect("frontend:project_list")

    def _build_context(self, *, form: MotivationForm) -> dict:
        return {
            "application": self.application,
            "project": self.application.project,
            "form": form,
        }
