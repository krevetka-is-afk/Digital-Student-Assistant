from pathlib import Path

from apps.base.admin_unfold import UnfoldModelAdmin
from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import ImportRun
from .services import run_epp_xlsx_import


class EppImportUploadForm(forms.Form):
    file = forms.FileField(
        label="EPP XLSX file",
        help_text="Choose an .xlsx file exported from EPP.",
        widget=forms.ClearableFileInput(
            attrs={
                "accept": ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            }
        ),
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if Path(upload.name).suffix.lower() != ".xlsx":
            raise forms.ValidationError("Upload an .xlsx file.")
        return upload


@admin.register(ImportRun)
class ImportRunAdmin(UnfoldModelAdmin):
    list_display = (
        "id",
        "source_name",
        "status",
        "imported_by_id",
        "started_at",
        "finished_at",
        "stats_summary",
    )
    list_filter = ("status", "source", "started_at")
    search_fields = ("source_name", "error_message")
    readonly_fields = (
        "source",
        "source_name",
        "status",
        "imported_by_id",
        "stats",
        "error_message",
        "started_at",
        "finished_at",
    )
    fields = readonly_fields
    change_list_template = "admin/imports/importrun/change_list.html"
    ordering = ("-started_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "epp-upload/",
                self.admin_site.admin_view(self.epp_upload_view),
                name="imports_importrun_epp_upload",
            ),
        ]
        return custom_urls + urls

    def epp_upload_view(self, request):
        form = EppImportUploadForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            upload = form.cleaned_data["file"]
            try:
                import_run = run_epp_xlsx_import(
                    upload=upload,
                    imported_by_id=request.user.id,
                )
            except Exception as exc:
                messages.error(request, f"EPP import failed: {exc}")
            else:
                stats = import_run.stats
                messages.success(
                    request,
                    "EPP import completed: "
                    f"{stats.get('projects_created', 0)} project(s) created, "
                    f"{stats.get('projects_updated', 0)} updated, "
                    f"{stats.get('skipped', 0)} skipped.",
                )
                return redirect("admin:imports_importrun_changelist")

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Import EPP XLSX",
            "form": form,
            "media": self.media + form.media,
            "changelist_url": reverse("admin:imports_importrun_changelist"),
        }
        return render(request, "admin/imports/importrun/upload_form.html", context)

    @admin.display(description="Stats")
    def stats_summary(self, obj):
        if not obj.stats:
            return "-"
        return format_html(
            "created: {}, updated: {}, skipped: {}, errors: {}",
            obj.stats.get("projects_created", 0),
            obj.stats.get("projects_updated", 0),
            obj.stats.get("skipped", 0),
            obj.stats.get("errors", 0),
        )
