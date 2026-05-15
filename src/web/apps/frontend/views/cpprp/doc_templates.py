from apps.account.models import DocumentTemplate
from apps.frontend.decorators import moderator_required
from apps.frontend.forms import TemplateForm
from apps.frontend.utils import LOGIN_URL, flash_form_errors
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .dashboard import _cpprp_tab_redirect


@login_required(login_url=LOGIN_URL)
@moderator_required
@require_POST
def cpprp_template_create(request):
    form = TemplateForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            with transaction.atomic():
                DocumentTemplate.objects.create(
                    slug=d["slug"],
                    title=d["title"],
                    url=d["url"],
                    audience=d["audience"],
                    description=d["description"],
                    is_active=d["is_active"],
                )
            messages.success(request, f"Шаблон «{d['title']}» добавлен.")
        except IntegrityError:
            messages.error(request, "Не удалось добавить шаблон — такой slug уже занят.")
    else:
        flash_form_errors(request, form)
    return _cpprp_tab_redirect("templates")

@login_required(login_url=LOGIN_URL)
@moderator_required
@require_POST
def cpprp_template_toggle(request, pk):
    tpl           = get_object_or_404(DocumentTemplate, pk=pk)
    tpl.is_active = not tpl.is_active
    tpl.save(update_fields=["is_active", "updated_at"])
    state = "активирован" if tpl.is_active else "деактивирован"
    messages.success(request, f"Шаблон «{tpl.title}» {state}.")
    return _cpprp_tab_redirect("templates")

@login_required(login_url=LOGIN_URL)
@moderator_required
@require_POST
def cpprp_template_delete(request, pk):
    tpl   = get_object_or_404(DocumentTemplate, pk=pk)
    title = tpl.title
    tpl.delete()
    messages.success(request, f"Шаблон «{title}» удалён.")
    return _cpprp_tab_redirect("templates")
