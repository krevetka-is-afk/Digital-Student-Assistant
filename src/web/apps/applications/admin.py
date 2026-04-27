from apps.base.admin_unfold import UnfoldModelAdmin
from django.contrib import admin

from .models import Application


@admin.register(Application)
class ApplicationAdmin(UnfoldModelAdmin):
    list_display = ("id", "project", "applicant", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("project__title", "applicant__username", "applicant__email")
