import csv

from apps.base.admin_unfold import UnfoldModelAdmin
from apps.projects.export_epp_xlsx import build_projects_xlsx_bytes
from django import forms
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path

from .models import EPP, Project, ProjectStatus, Technology, TechnologyStatus


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
class ProjectAdmin(UnfoldModelAdmin):
    form = ProjectAdminForm
    list_display = ("id", "title", "status", "owner", "updated_at", "source_type", "created_at")
    list_filter = ("status", "owner", "source_type", "created_at")
    search_fields = ("title", "description", "owner__username", "owner__email")
    list_select_related = ("owner",)
    autocomplete_fields = ("owner",)
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    actions = (
        "publish_selected",
        "archive_selected",
        "export_selected_as_csv",
        "export_selected_as_epp_xlsx",
    )
    change_list_template = "admin/projects/project/change_list.html"
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "export-all/",
                self.admin_site.admin_view(self.export_all_as_csv_view),
                name="projects_project_export_all",
            ),
            path(
                "export-all-xlsx/",
                self.admin_site.admin_view(self.export_all_as_epp_xlsx_view),
                name="projects_project_export_all_xlsx",
            ),
        ]
        return custom_urls + urls

    def export_all_as_csv_view(self, request):
        return self.export_selected_as_csv(request, Project.objects.order_by("pk"))

    def export_all_as_epp_xlsx_view(self, request):
        return self.export_selected_as_epp_xlsx(request, Project.objects.order_by("pk"))

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

    @admin.action(description="Export selected projects as CSV")
    def export_selected_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="projects-export.csv"'
        response.write("\ufeff")  # BOM for Excel UTF-8 compatibility

        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "title",
                "status",
                "source_type",
                "team_size",
                "accepted_participants_count",
                "education_program",
                "study_course",
                "created_at",
            ]
        )
        for project in queryset.order_by("pk"):
            writer.writerow(
                [
                    project.pk,
                    project.title,
                    project.status,
                    project.source_type,
                    project.team_size,
                    project.accepted_participants_count,
                    project.education_program,
                    project.study_course,
                    project.created_at.strftime("%Y-%m-%d %H:%M") if project.created_at else "",
                ]
            )
        return response

    @admin.action(description="Export selected projects as EPP XLSX (compatible + extended)")
    def export_selected_as_epp_xlsx(self, request, queryset):
        payload = build_projects_xlsx_bytes(queryset, variant="both")
        response = HttpResponse(
            payload,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = 'attachment; filename="projects-export-both.xlsx"'
        return response


@admin.register(Technology)
class TechnologyAdmin(UnfoldModelAdmin):
    list_display = ("id", "normalized_name", "status", "created_by", "updated_at")
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("name", "normalized_name", "created_by__username", "created_by__email")
    list_select_related = ("created_by",)
    autocomplete_fields = ("created_by",)
    readonly_fields = ("created_at", "updated_at")
    actions = ("approve_selected", "reject_selected")

    @admin.action(description="Approve selected technologies")
    def approve_selected(self, request, queryset):
        updated = queryset.exclude(status=TechnologyStatus.APPROVED).update(
            status=TechnologyStatus.APPROVED
        )
        self.message_user(request, f"Approved {updated} technology(s).")

    @admin.action(description="Reject selected technologies")
    def reject_selected(self, request, queryset):
        updated = queryset.exclude(status=TechnologyStatus.REJECTED).update(
            status=TechnologyStatus.REJECTED
        )
        self.message_user(request, f"Rejected {updated} technology(s).")


@admin.register(EPP)
class EPPAdmin(UnfoldModelAdmin):
    list_display = ("id", "source_ref", "title", "campaign_title", "status_raw", "updated_at")
    search_fields = ("source_ref", "title", "campaign_title", "supervisor_email")
    readonly_fields = ("created_at", "updated_at")
