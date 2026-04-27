from django.contrib import admin

from .models import (
    FacultyAuthorship,
    FacultyCourse,
    FacultyPerson,
    FacultyPublication,
    FacultySyncState,
    ProjectFacultyMatch,
)


@admin.register(FacultyPerson)
class FacultyPersonAdmin(admin.ModelAdmin):
    list_display = ("full_name", "source_key", "primary_unit", "publications_total", "is_stale")
    search_fields = ("full_name", "source_person_id", "source_profile_url", "primary_unit")
    list_filter = ("is_stale", "campus_name")


@admin.register(FacultyPublication)
class FacultyPublicationAdmin(admin.ModelAdmin):
    list_display = ("title", "source_publication_id", "publication_type", "year")
    search_fields = ("title", "source_publication_id")
    list_filter = ("publication_type", "year")


@admin.register(FacultyAuthorship)
class FacultyAuthorshipAdmin(admin.ModelAdmin):
    list_display = ("publication", "person", "position", "display_name")
    search_fields = ("display_name", "publication__title", "person__full_name")


@admin.register(FacultyCourse)
class FacultyCourseAdmin(admin.ModelAdmin):
    list_display = ("title", "person", "academic_year", "language", "level")
    search_fields = ("title", "person__full_name")
    list_filter = ("academic_year", "language", "level")


@admin.register(FacultySyncState)
class FacultySyncStateAdmin(admin.ModelAdmin):
    list_display = ("resource", "last_success_at", "last_error", "updated_at")
    search_fields = ("resource",)


@admin.register(ProjectFacultyMatch)
class ProjectFacultyMatchAdmin(admin.ModelAdmin):
    list_display = ("project", "faculty_person", "status", "match_strategy", "confidence")
    search_fields = ("project__title", "faculty_person__full_name", "supervisor_name")
    list_filter = ("status", "match_strategy")
