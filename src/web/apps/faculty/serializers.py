from rest_framework import serializers

from .models import (
    FacultyAuthorship,
    FacultyCourse,
    FacultyPerson,
    FacultyPublication,
    ProjectFacultyMatch,
)


class FacultyPersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacultyPerson
        fields = [
            "source_key",
            "source_person_id",
            "source_profile_url",
            "full_name",
            "full_name_normalized",
            "primary_unit",
            "primary_unit_normalized",
            "campus_id",
            "campus_name",
            "publications_total",
            "interests",
            "languages",
            "is_stale",
            "source_hash",
            "updated_at",
        ]
        read_only_fields = fields


class FacultyAuthorshipSerializer(serializers.ModelSerializer):
    person_source_key = serializers.SerializerMethodField()

    class Meta:
        model = FacultyAuthorship
        fields = [
            "person_source_key",
            "position",
            "display_name",
            "href",
        ]
        read_only_fields = fields

    def get_person_source_key(self, obj) -> str | None:
        return obj.person.source_key if obj.person_id else None


class FacultyPublicationSerializer(serializers.ModelSerializer):
    authors = FacultyAuthorshipSerializer(source="authorships", many=True, read_only=True)

    class Meta:
        model = FacultyPublication
        fields = [
            "source_publication_id",
            "title",
            "publication_type",
            "year",
            "language",
            "url",
            "created_at_source",
            "authors",
            "source_hash",
            "updated_at",
        ]
        read_only_fields = fields


class FacultyCourseSerializer(serializers.ModelSerializer):
    person_source_key = serializers.CharField(source="person.source_key", read_only=True)

    class Meta:
        model = FacultyCourse
        fields = [
            "course_key",
            "person_source_key",
            "title",
            "url",
            "academic_year",
            "language",
            "level",
            "source_hash",
            "updated_at",
        ]
        read_only_fields = fields


class ProjectFacultyMatchSerializer(serializers.ModelSerializer):
    faculty_source_key = serializers.CharField(source="faculty_person.source_key", read_only=True)

    class Meta:
        model = ProjectFacultyMatch
        fields = [
            "project_id",
            "faculty_source_key",
            "status",
            "match_strategy",
            "confidence",
            "supervisor_name",
            "supervisor_email",
            "supervisor_department",
            "candidate_person_ids",
            "matched_at",
            "updated_at",
        ]
        read_only_fields = fields


class ProjectFacultyMatchPublicSerializer(serializers.ModelSerializer):
    faculty_source_key = serializers.CharField(source="faculty_person.source_key", read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True)

    class Meta:
        model = ProjectFacultyMatch
        fields = [
            "project_id",
            "project_title",
            "faculty_source_key",
            "status",
            "match_strategy",
            "confidence",
            "supervisor_name",
            "supervisor_department",
            "matched_at",
        ]
        read_only_fields = fields
