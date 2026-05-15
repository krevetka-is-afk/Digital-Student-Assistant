import pytest


@pytest.mark.parametrize(
    "value, expected",
    [
        ("", set()),
        ("Python", {"python"}),
        ("Python Django", {"python", "django"}),
        ("C++", {"c++"}),
        ("C++#ML", {"c++#ml"}),
        ("hello-world", {"hello-world"}),
        ("   ", set()),
        ("Python,Django", {"python", "django"}),
        ("3.14", {"3.14"}),
        ("react.js", {"react.js"}),
    ],
)
def test_tokenize(value, expected):
    from apps.recs.services import _tokenize

    assert _tokenize(value) == expected


_DEFAULT_REASON = "semantic match"


@pytest.mark.parametrize(
    "items, expected",
    [
        (None, None),
        ("a string", None),
        (42, None),
        ([], []),
        (
            [{"project_id": 1, "score": 0.9, "reason": "good match"}],
            [{"project_id": 1, "score": 0.9, "reason": "good match"}],
        ),
        (
            [{"project_id": 1}],
            [{"project_id": 1, "score": 0.0, "reason": _DEFAULT_REASON}],
        ),
        (
            [{"project_id": "bad_id"}],
            [],
        ),
        (
            [{"project_id": 1, "score": "0.75", "reason": None}],
            [{"project_id": 1, "score": 0.75, "reason": _DEFAULT_REASON}],
        ),
        (
            [{"project_id": 1}, "not_a_dict", {"project_id": 2}],
            [
                {"project_id": 1, "score": 0.0, "reason": _DEFAULT_REASON},
                {"project_id": 2, "score": 0.0, "reason": _DEFAULT_REASON},
            ],
        ),
    ],
)
def test_normalize_remote_items(items, expected):
    from apps.recs.services import _normalize_remote_items

    assert _normalize_remote_items(items) == expected


def _project_form(tech_tags_raw: str):

    from apps.frontend.forms import ProjectFrontendForm

    return ProjectFrontendForm(
        data={
            "title": "Test Project",
            "description": "A test description.",
            "tech_tags_raw": tech_tags_raw,
            "team_size": 3,
        }
    )


def test_tags_empty_string_returns_empty_list():
    form = _project_form("")
    assert form.is_valid(), form.errors
    assert form.cleaned_data["tech_tags_raw"] == []


def test_tags_single_tag():
    form = _project_form("Python")
    assert form.is_valid(), form.errors
    assert form.cleaned_data["tech_tags_raw"] == ["python"]


def test_tags_multiple_comma_separated():
    form = _project_form("Python, Django, React")
    assert form.is_valid(), form.errors
    assert form.cleaned_data["tech_tags_raw"] == ["python", "django", "react"]


def test_tags_deduplicated_case_insensitive():
    form = _project_form("Python, python, PYTHON")
    assert form.is_valid(), form.errors
    assert form.cleaned_data["tech_tags_raw"] == ["python"]


def test_tags_too_many_raises_validation_error():
    from apps.frontend.forms.projects import _TAGS_MAX

    many_tags = ",".join(f"tag{i}" for i in range(_TAGS_MAX + 1))
    form = _project_form(many_tags)
    assert not form.is_valid()
    assert "tech_tags_raw" in form.errors


def test_tags_with_special_chars_accepted():
    form = _project_form("C++, React.js, ASP.NET")
    assert form.is_valid(), form.errors
    assert form.cleaned_data["tech_tags_raw"] == ["c++", "react.js", "asp.net"]


def test_tags_starting_with_at_sign_rejected():
    form = _project_form("@invalid")
    assert not form.is_valid()
    assert "tech_tags_raw" in form.errors


def test_tags_too_long_single_tag_rejected():
    long_tag = "a" * 51
    form = _project_form(long_tag)
    assert not form.is_valid()
    assert "tech_tags_raw" in form.errors


def test_build_graph_data_empty_input():
    from apps.frontend.views.projects.catalog import _build_graph_data

    nodes, edges = _build_graph_data([])
    assert nodes == []
    assert edges == []


def test_build_graph_data_single_article_single_author():
    from apps.frontend.views.projects.catalog import _build_graph_data

    articles = [{"title": "Paper A", "authors": ["Alice"]}]
    nodes, edges = _build_graph_data(articles)
    assert len(nodes) == 1
    assert nodes[0]["label"] == "Alice"
    assert nodes[0]["value"] == 1
    assert edges == []


def test_build_graph_data_two_authors_one_article():
    from apps.frontend.views.projects.catalog import _build_graph_data

    articles = [{"title": "Paper A", "authors": ["Alice", "Bob"]}]
    nodes, edges = _build_graph_data(articles)
    assert len(nodes) == 2
    assert len(edges) == 1
    assert edges[0]["value"] == 1


def test_build_graph_data_repeated_coauthorship_increases_edge_weight():
    from apps.frontend.views.projects.catalog import _build_graph_data

    articles = [
        {"title": "Paper A", "authors": ["Alice", "Bob"]},
        {"title": "Paper B", "authors": ["Alice", "Bob"]},
    ]
    nodes, edges = _build_graph_data(articles)
    assert len(edges) == 1
    assert edges[0]["value"] == 2


def test_build_graph_data_node_value_equals_article_count():
    from apps.frontend.views.projects.catalog import _build_graph_data

    articles = [
        {"title": "P1", "authors": ["Alice", "Bob"]},
        {"title": "P2", "authors": ["Alice", "Carol"]},
    ]
    nodes, edges = _build_graph_data(articles)
    by_label = {n["label"]: n for n in nodes}
    assert by_label["Alice"]["value"] == 2
    assert by_label["Bob"]["value"] == 1
    assert by_label["Carol"]["value"] == 1

    assert len(edges) == 2
