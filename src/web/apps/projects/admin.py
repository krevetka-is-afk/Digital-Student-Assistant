from django import forms
from django.contrib import admin

from .models import EPP, Project, ProjectStatus


class ProjectAdminForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = "__all__"
        help_texts = {
            "tech_tags": 'List technologies as JSON array, e.g. ["Django", "PostgreSQL"].',
            "extra_data": "Optional JSON metadata from external sources. \
                Leave empty unless needed.",
        }


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    form = ProjectAdminForm
    list_display = ("id", "title", "status", "owner", "updated_at", "source_type", "created_at")
    list_filter = ("status", "owner", "source_type", "created_at")
    search_fields = ("title", "description", "owner__username", "owner__email")
    list_select_related = ("owner",)
    autocomplete_fields = ("owner",)
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    actions = ("publish_selected", "archive_selected")
    fieldsets = (
        (
            "Core information",
            {"fields": ("title", "vacancy_title", "description", "owner", "status")},
        ),
        (
            "Source and tags",
            {
                "fields": (
                    "epp",
                    "source_type",
                    "source_ref",
                    "source_row_index",
                    "status_raw",
                    "tech_tags",
                ),
                "description": "Use source details only when project \
                    data comes from an external import.",
            },
        ),
        (
            "Additional metadata",
            {"fields": ("extra_data", "raw_payload"), "classes": ("collapse",)},
        ),
        ("System fields", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.action(description="Publish selected projects")
    def publish_selected(self, request, queryset):
        updated = queryset.exclude(status=ProjectStatus.PUBLISHED).update(
            status=ProjectStatus.PUBLISHED
        )
        self.message_user(request, f"Published {updated} project(s).")

    @admin.action(description="Archive selected projects")
    def archive_selected(self, request, queryset):
        updated = queryset.exclude(status=ProjectStatus.ARCHIVED).update(
            status=ProjectStatus.ARCHIVED
        )
        self.message_user(request, f"Archived {updated} project(s).")


@admin.register(EPP)
class EPPAdmin(admin.ModelAdmin):
    list_display = ("id", "source_ref", "title", "campaign_title", "status_raw", "updated_at")
    search_fields = ("source_ref", "title", "campaign_title", "supervisor_email")
    readonly_fields = ("created_at", "updated_at")
