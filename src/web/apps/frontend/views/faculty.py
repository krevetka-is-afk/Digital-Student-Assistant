from apps.faculty.models import (
    FacultyCourse,
    FacultyMatchStatus,
    FacultyPerson,
    ProjectFacultyMatch,
)
from apps.frontend.utils import LOGIN_URL
from apps.projects.models import ProjectStatus
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

_PAGE_SIZE = 12


@login_required(login_url=LOGIN_URL)
def faculty_list(request):
    query = request.GET.get("q", "").strip()
    queryset = FacultyPerson.objects.filter(is_stale=False).order_by("full_name")
    if query:
        queryset = queryset.filter(full_name__icontains=query)
    page_number = request.GET.get("page", 1)
    paginator = Paginator(queryset, _PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "frontend/faculty_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "total": paginator.count,
        },
    )


@login_required(login_url=LOGIN_URL)
def faculty_detail(request, source_key):
    person = get_object_or_404(FacultyPerson, source_key=source_key, is_stale=False)
    projects = list(
        ProjectFacultyMatch.objects.select_related("project")
        .filter(
            faculty_person=person,
            status=FacultyMatchStatus.CONFIRMED,
            project__status__in=ProjectStatus.catalog_values(),
        )
        .order_by("project_id")
    )
    courses = list(FacultyCourse.objects.filter(person=person).order_by("-academic_year", "title"))
    return render(
        request,
        "frontend/faculty_detail.html",
        {
            "person": person,
            "projects": projects,
            "courses": courses,
        },
    )
