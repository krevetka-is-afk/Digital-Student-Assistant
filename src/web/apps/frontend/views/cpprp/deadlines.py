from apps.account.models import PlatformDeadline
from apps.frontend.decorators import moderator_required
from apps.frontend.forms import DeadlineForm
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
def cpprp_deadline_create(request):
    form = DeadlineForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            with transaction.atomic():
                PlatformDeadline.objects.create(
                    slug=d["slug"],
                    title=d["title"],
                    audience=d["audience"],
                    description=d["description"],
                    starts_at=d["starts_at"],
                    ends_at=d["ends_at"],
                    is_active=d["is_active"],
                )
            messages.success(request, f"Дедлайн «{d['title']}» создан.")
        except IntegrityError:
            messages.error(request, "Не удалось создать дедлайн — такой slug уже занят.")
    else:
        flash_form_errors(request, form)
    return _cpprp_tab_redirect("deadlines")


@login_required(login_url=LOGIN_URL)
@moderator_required
@require_POST
def cpprp_deadline_toggle(request, pk):
    dl = get_object_or_404(PlatformDeadline, pk=pk)
    dl.is_active = not dl.is_active
    dl.save(update_fields=["is_active", "updated_at"])
    state = "активирован" if dl.is_active else "деактивирован"
    messages.success(request, f"Дедлайн «{dl.title}» {state}.")
    return _cpprp_tab_redirect("deadlines")


@login_required(login_url=LOGIN_URL)
@moderator_required
@require_POST
def cpprp_deadline_delete(request, pk):
    dl = get_object_or_404(PlatformDeadline, pk=pk)
    title = dl.title
    dl.delete()
    messages.success(request, f"Дедлайн «{title}» удалён.")
    return _cpprp_tab_redirect("deadlines")
