from django.contrib import messages
from django.urls import reverse_lazy

LOGIN_URL = reverse_lazy("frontend:auth")


def flash_form_errors(request, form) -> None:
    for field_errors in form.errors.values():
        for error in field_errors:
            messages.error(request, error)
