import csv

from apps.applications.models import Application
from apps.frontend.decorators import moderator_required
from apps.frontend.utils import LOGIN_URL
from apps.projects.models import Project
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required(login_url=LOGIN_URL)
@moderator_required
def cpprp_export_projects(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="projects-export.csv"'
    response.write("﻿")

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
    for p in Project.objects.order_by("pk").iterator():
        writer.writerow(
            [
                p.pk,
                p.title,
                p.status,
                p.source_type,
                p.team_size,
                p.accepted_participants_count,
                p.education_program,
                p.study_course,
                p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
            ]
        )
    return response


@login_required(login_url=LOGIN_URL)
@moderator_required
def cpprp_export_applications(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="applications-export.csv"'
    response.write("﻿")

    writer = csv.writer(response)
    writer.writerow(
        [
            "id",
            "project_id",
            "project_title",
            "applicant_id",
            "applicant_email",
            "status",
            "created_at",
        ]
    )
    for a in Application.objects.select_related("project", "applicant").order_by("pk").iterator():
        writer.writerow(
            [
                a.pk,
                a.project_id,
                a.project.title,
                a.applicant_id,
                a.applicant.email,
                a.status,
                a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
            ]
        )
    return response


@login_required(login_url=LOGIN_URL)
@moderator_required
def cpprp_export_projects_xlsx(request):

    from apps.projects.export_epp_xlsx import LegacyVariant, build_projects_xlsx_bytes

    variant_raw = (request.GET.get("variant") or "both").lower()
    variant: LegacyVariant = (
        variant_raw if variant_raw in ("compatible", "extended", "both") else "both"
    )
    payload = build_projects_xlsx_bytes(Project.objects.all(), variant=variant)
    response = HttpResponse(
        payload,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="projects-export-{variant}.xlsx"'
    return response
