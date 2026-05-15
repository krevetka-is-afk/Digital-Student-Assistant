from uuid import uuid4

import pytest
from apps.faculty.models import FacultyAuthorship, FacultyPublication
from apps.frontend.views.projects.catalog import _fetch_faculty_publications
from django.core.cache import cache

pytestmark = pytest.mark.django_db


def _uid():
    return uuid4().hex[:8]


def _make_publication(**overrides):
    defaults = {
        "source_publication_id": f"test-{_uid()}",
        "title": "Test Publication",
        "publication_type": "ARTICLE",
        "year": 2023,
        "url": "https://doi.org/test",
        "source_hash": _uid(),
        "raw_payload": {},
    }
    defaults.update(overrides)
    return FacultyPublication.objects.create(**defaults)


@pytest.fixture(autouse=True)
def clear_faculty_cache():
    cache.clear()
    yield
    cache.clear()


class TestFetchFacultyPublications:
    def test_returns_empty_when_no_publications(self):
        assert _fetch_faculty_publications() == []

    def test_extracts_venue_from_raw_payload(self):
        _make_publication(raw_payload={"venue": "Journal of AI. 2023. Vol. 1."})
        result = _fetch_faculty_publications()
        assert len(result) == 1
        assert result[0]["venue"] == "Journal of AI. 2023. Vol. 1."

    def test_falls_back_to_journal_key_for_venue(self):
        _make_publication(raw_payload={"journal": "Nature. 2022."})
        result = _fetch_faculty_publications()
        assert result[0]["venue"] == "Nature. 2022."

    def test_venue_empty_when_not_in_raw_payload(self):
        _make_publication(raw_payload={})
        result = _fetch_faculty_publications()
        assert result[0]["venue"] == ""

    def test_extracts_keywords_from_raw_payload(self):
        _make_publication(raw_payload={"keywords": ["machine learning", "deep learning"]})
        result = _fetch_faculty_publications()
        assert result[0]["keywords"] == ["machine learning", "deep learning"]

    def test_keywords_empty_when_not_in_raw_payload(self):
        _make_publication(raw_payload={})
        result = _fetch_faculty_publications()
        assert result[0]["keywords"] == []

    def test_non_list_keywords_coerced_to_empty(self):
        _make_publication(raw_payload={"keywords": "not-a-list"})
        result = _fetch_faculty_publications()
        assert result[0]["keywords"] == []

    def test_direction_maps_publication_type_to_russian(self):
        _make_publication(raw_payload={}, publication_type="ARTICLE")
        result = _fetch_faculty_publications()
        assert result[0]["direction"] == "Статья"

    def test_direction_falls_back_to_raw_type_if_unknown(self):
        _make_publication(raw_payload={}, publication_type="UNKNOWN_TYPE")
        result = _fetch_faculty_publications()
        assert result[0]["direction"] == "UNKNOWN_TYPE"

    def test_authors_from_authorships(self):
        pub = _make_publication(raw_payload={})
        FacultyAuthorship.objects.create(
            publication=pub,
            position=0,
            display_name="Иванов А. В.",
        )
        result = _fetch_faculty_publications()
        assert result[0]["authors"] == ["Иванов А. В."]

    def test_authors_ordered_by_position(self):
        pub = _make_publication(raw_payload={})
        FacultyAuthorship.objects.create(publication=pub, position=1, display_name="Б. Б.")
        FacultyAuthorship.objects.create(publication=pub, position=0, display_name="А. А.")
        result = _fetch_faculty_publications()
        assert result[0]["authors"] == ["А. А.", "Б. Б."]

    def test_result_cached_on_second_call(self):
        _make_publication(raw_payload={"venue": "Cached Journal"})
        first = _fetch_faculty_publications()
        second = _fetch_faculty_publications()
        assert first == second
        assert first[0]["venue"] == "Cached Journal"
