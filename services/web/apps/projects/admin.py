from django import forms
from django.contrib import admin

from .models import Project, ProjectStatus


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
        ("Core information", {"fields": ("title", "description", "owner", "status")}),
        (
            "Source and tags",
            {
                "fields": ("source_type", "source_ref", "tech_tags"),
                "description": "Use source details only when project \
                    data comes from an external import.",
            },
        ),
        ("Additional metadata", {"fields": ("extra_data",), "classes": ("collapse",)}),
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
