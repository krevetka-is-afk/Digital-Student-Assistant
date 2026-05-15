import hashlib
import json
import logging
import os
from collections import Counter, defaultdict
from typing import cast

from apps.applications.models import Application, ApplicationStatus
from apps.faculty.models import FacultyAuthorship, FacultyPerson, FacultyPublication
from apps.frontend.decorators import customer_required
from apps.frontend.utils import LOGIN_URL
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from apps.projects.normalization import normalize_technology_tag, normalize_technology_tags
from apps.projects.utils import collect_all_tags
from apps.users.models import UserRole
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import redirect, render

from . import PAGE_SIZE

logger = logging.getLogger(__name__)

RECOMMENDED_COUNT = 6
_RECS_CACHE_TTL = 300
_FACULTY_CACHE_TTL = 3600

_CUSTOMER_STATUSES = (
    ProjectStatus.DRAFT,
    ProjectStatus.ON_MODERATION,
    ProjectStatus.PUBLISHED,
    ProjectStatus.STAFFED,
    ProjectStatus.REJECTED,
)

_PUB_TYPE_RU = {
    "ARTICLE": "Статья",
    "BOOK": "Книга",
    "PREPRINT": "Препринт",
    "CHAPTER": "Глава в книге",
    "CONFERENCE": "Конференция",
    "THESIS": "Диссертация",
    "OTHER": "Прочее",
}


@login_required(login_url=LOGIN_URL)
def project_list(request):
    try:
        _role = request.user.profile.role
    except Exception:
        _role = ""
    if _role == UserRole.CUSTOMER:
        return redirect("frontend:my_projects")
    _is_student = _role == UserRole.STUDENT

    q = request.GET.get("q", "").strip()
    tech_tags_filter = request.GET.getlist("tech_tags")
    team_size_filter = request.GET.get("team_size", "").strip()
    source_type_filter = request.GET.get("source_type", "").strip()
    page_number = request.GET.get("page", 1)

    queryset = Project.objects.filter(status=ProjectStatus.PUBLISHED).select_related("owner")

    if q:
        queryset = queryset.filter(Q(title__icontains=q) | Q(description__icontains=q))

    for tag in tech_tags_filter:
        normalized_tag = normalize_technology_tag(tag)
        if normalized_tag:
            queryset = queryset.filter(
                Q(technologies__normalized_name=normalized_tag)
                | Q(tech_tags__icontains=normalized_tag)
            ).distinct()

    if team_size_filter:
        try:
            queryset = queryset.filter(team_size=int(team_size_filter))
        except ValueError:
            pass

    if source_type_filter and source_type_filter in {
        ProjectSourceType.SUPERVISOR,
        ProjectSourceType.INITIATIVE,
        ProjectSourceType.EPP,
        ProjectSourceType.MANUAL,
    }:
        queryset = queryset.filter(source_type=source_type_filter)

    queryset = queryset.order_by("-created_at")
    paginator = Paginator(queryset, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    is_filtered = bool(q or tech_tags_filter or team_size_filter or source_type_filter)
    visible_ids = [p.id for p in page_obj.object_list]

    apps = Application.objects.filter(
        applicant=request.user,
        project_id__in=visible_ids,
    ).values("project_id", "status")
    user_applications = {a["project_id"]: a["status"] for a in apps}

    user_interests: list[str] = []
    if _is_student:
        try:
            user_interests = normalize_technology_tags(request.user.profile.interests or [])
        except Exception:
            pass

    context: dict = {
        "page_obj": page_obj,
        "query": q,
        "tech_tags_filter": tech_tags_filter,
        "team_size_filter": team_size_filter,
        "source_type_filter": source_type_filter,
        "user_applications": user_applications,
        "all_tags": collect_all_tags(),
        "is_filtered": is_filtered,
        "user_interests": user_interests,
        "ApplicationStatus": ApplicationStatus,
        "ProjectStatus": ProjectStatus,
        "ProjectSourceType": ProjectSourceType,
        "show_recs_tab": False,
        "rec_projects": [],
        "rec_reasons": {},
        "rec_mode": None,
        "has_interests": False,
        "rec_user_applications": {},
        "show_applications_tab": False,
        "app_page_obj": None,
        "app_counts": {},
        "suggested_interests": [],
        "show_bookmarks_tab": True,
        "bookmarked_ids": set(),
        "bookmark_page_obj": None,
        "bookmark_user_applications": {},
    }

    if _is_student:
        context.update(_student_catalog_context(request))

    context.update(_bookmark_context(request))

    if request.headers.get("HX-Request") and request.headers.get("HX-Target") == "projects-section":
        return render(request, "frontend/partials/projects_grid.html", context)

    return render(request, "frontend/project_list.html", context)


def _student_catalog_context(request) -> dict:
    rec_projects: list = []
    rec_reasons: dict = {}
    rec_mode = None
    try:
        rec_projects, rec_reasons, rec_mode = _get_recommendations(request)
    except Exception:
        logger.warning("_get_recommendations failed in project_list", exc_info=True)

    has_interests = bool(getattr(getattr(request.user, "profile", None), "interests", None))

    rec_user_applications: dict = {}
    rec_ids = [p.id for p in rec_projects]
    if rec_ids:
        rec_apps = Application.objects.filter(
            applicant=request.user,
            project_id__in=rec_ids,
        ).values("project_id", "status")
        rec_user_applications = {a["project_id"]: a["status"] for a in rec_apps}

    all_applications = list(
        Application.objects.filter(applicant=request.user)
        .select_related("project", "project__owner")
        .order_by("-created_at")
    )
    app_counts = {
        "total": len(all_applications),
        "submitted": sum(1 for a in all_applications if a.status == ApplicationStatus.SUBMITTED),
        "accepted": sum(1 for a in all_applications if a.status == ApplicationStatus.ACCEPTED),
        "rejected": sum(1 for a in all_applications if a.status == ApplicationStatus.REJECTED),
    }

    app_paginator = Paginator(all_applications, 5)
    app_page_number = request.GET.get("app_page", 1)
    app_page_obj = app_paginator.get_page(app_page_number)

    suggested_interests: list[str] = []
    if not has_interests:
        fav_ids = list(request.user.profile.favorite_project_ids)
        applied_ids = [a.project_id for a in all_applications]
        activity_ids = list({*fav_ids, *applied_ids})[:20]
        if activity_ids:
            tag_counts: Counter = Counter()
            for _p in Project.objects.filter(pk__in=activity_ids).only("tech_tags"):
                for _tag in _p.tech_tags or []:
                    tag_counts[_tag] += 1
            suggested_interests = [t for t, _ in tag_counts.most_common(6)]

    owned_initiative_projects = list(
        Project.objects.filter(
            owner=request.user,
            source_type=ProjectSourceType.INITIATIVE,
        ).order_by("-created_at")
    )

    return {
        "show_recs_tab": True,
        "rec_projects": rec_projects,
        "rec_reasons": rec_reasons,
        "rec_mode": rec_mode,
        "has_interests": has_interests,
        "rec_user_applications": rec_user_applications,
        "show_applications_tab": True,
        "app_page_obj": app_page_obj,
        "app_counts": app_counts,
        "suggested_interests": suggested_interests,
        "owned_initiative_projects": owned_initiative_projects,
    }


def _bookmark_context(request) -> dict:
    fav_ids = list(request.user.profile.favorite_project_ids)
    bookmarked_ids = set(fav_ids)
    bookmark_page_obj: object = None
    bookmark_user_applications: dict = {}

    if fav_ids:
        bm_queryset = Project.objects.filter(pk__in=fav_ids).select_related("owner").order_by("-pk")
        bookmark_page_number = request.GET.get("bookmark_page", 1)
        bm_paginator = Paginator(bm_queryset, PAGE_SIZE)
        bookmark_page_obj = bm_paginator.get_page(bookmark_page_number)
        bm_apps = Application.objects.filter(
            applicant=request.user,
            project_id__in=fav_ids,
        ).values("project_id", "status")
        bookmark_user_applications = {a["project_id"]: a["status"] for a in bm_apps}

    return {
        "show_bookmarks_tab": True,
        "bookmarked_ids": bookmarked_ids,
        "bookmark_page_obj": bookmark_page_obj,
        "bookmark_user_applications": bookmark_user_applications,
    }


def _get_recommendations(request):
    from apps.recs.services import recommend_projects

    try:
        interests = list(request.user.profile.interests or [])
    except Exception:
        interests = []

    if interests:
        interests_hash = hashlib.sha256(json.dumps(sorted(interests)).encode()).hexdigest()[:16]
        cache_key = f"recs:u{request.user.pk}:{interests_hash}"

        cached = cache.get(cache_key)
        if cached is not None:
            cached_mode, raw_items = cached
            pk_list = [item["pk"] for item in raw_items]
            project_by_pk = {
                p.pk: p for p in Project.objects.filter(pk__in=pk_list).select_related("owner")
            }
            projects = [
                project_by_pk[item["pk"]] for item in raw_items if item["pk"] in project_by_pk
            ]
            reasons = {
                item["pk"]: item["reason"] for item in raw_items if item["pk"] in project_by_pk
            }
            return projects, reasons, cached_mode

        try:
            mode, items = recommend_projects(interests, limit=RECOMMENDED_COUNT)
            projects = [cast(Project, item["project"]) for item in items]
            reasons = {cast(Project, item["project"]).pk: item["reason"] for item in items}
            raw_items = [
                {"pk": cast(Project, item["project"]).pk, "reason": item["reason"]}
                for item in items
            ]
            if projects:
                cache.set(cache_key, (mode, raw_items), timeout=_RECS_CACHE_TTL)
                return projects, reasons, mode
        except Exception:
            logger.warning("recs.service failed, falling back to latest projects", exc_info=True)

    projects = list(
        Project.objects.filter(status=ProjectStatus.PUBLISHED)
        .select_related("owner")
        .order_by("-created_at")[:RECOMMENDED_COUNT]
    )
    return projects, {}, None


@login_required(login_url=LOGIN_URL)
@customer_required
def my_projects(request):
    page_number = request.GET.get("page", 1)
    status_filter = request.GET.get("status", "").strip()

    base_qs = Project.objects.filter(owner=request.user)
    queryset = base_qs.order_by("-created_at")

    if status_filter:
        queryset = queryset.filter(status=status_filter)

    counts = base_qs.aggregate(
        total=Count("pk"), **{s: Count("pk", filter=Q(status=s)) for s in _CUSTOMER_STATUSES}
    )

    paginator = Paginator(queryset, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    app_agg = Application.objects.filter(project__owner=request.user).aggregate(
        total=Count("pk"),
        pending=Count("pk", filter=Q(status=ApplicationStatus.SUBMITTED)),
        accepted=Count("pk", filter=Q(status=ApplicationStatus.ACCEPTED)),
    )

    projects_with_pending = list(
        Project.objects.filter(owner=request.user)
        .annotate(
            pending_count=Count(
                "applications",
                filter=Q(applications__status=ApplicationStatus.SUBMITTED),
            ),
        )
        .filter(pending_count__gt=0)
        .order_by("-pending_count")[:8]
    )

    published_qs = list(base_qs.filter(status=ProjectStatus.PUBLISHED))
    spots_left_total = sum(
        max(0, p.team_size - p.accepted_participants_count) for p in published_qs
    )

    dashboard = {
        "total_apps": app_agg["total"] or 0,
        "pending_apps": app_agg["pending"] or 0,
        "accepted_apps": app_agg["accepted"] or 0,
        "active_projects": counts.get(ProjectStatus.PUBLISHED, 0),
        "on_moderation": counts.get(ProjectStatus.ON_MODERATION, 0),
        "spots_left_total": spots_left_total,
        "projects_with_pending": projects_with_pending,
    }

    raw_articles = _fetch_faculty_publications()
    articles = raw_articles or _get_sample_articles()
    using_faculty_data = bool(raw_articles)

    raw_staff = _fetch_faculty_staff()
    staff = raw_staff or _get_sample_staff()

    graph_nodes, graph_edges = _fetch_coauthorship_graph()
    graph_from_neo4j = bool(graph_nodes)
    if not graph_nodes:
        _graph_src = [a for a in articles if a.get("authors")] or _get_sample_articles()
        graph_nodes, graph_edges = _build_graph_data(_graph_src)

    if graph_from_neo4j:
        _graph_source_label = "neo4j"
        _graph_articles_count = FacultyPublication.objects.count()
    elif using_faculty_data:
        _graph_source_label = "postgresql"
        _graph_articles_count = len(articles)
    else:
        _graph_source_label = "demo"
        _graph_articles_count = len(articles)

    article_years = sorted(
        {a["year"] for a in articles if a.get("year")},
        reverse=True,
    )
    article_directions = sorted(
        {a["direction"] for a in articles if a.get("direction")},
    )

    return render(
        request,
        "frontend/my_projects.html",
        {
            "page_obj": page_obj,
            "status_filter": status_filter,
            "ProjectStatus": ProjectStatus,
            "ApplicationStatus": ApplicationStatus,
            "counts": counts,
            "total_count": counts["total"],
            "dashboard": dashboard,
            "sample_articles": articles,
            "article_years": article_years,
            "article_directions": article_directions,
            "sample_staff": staff,
            "graph_nodes_json": json.dumps(graph_nodes, ensure_ascii=False),
            "graph_edges_json": json.dumps(graph_edges, ensure_ascii=False),
            "using_faculty_data": using_faculty_data,
            "graph_source": _graph_source_label,
            "graph_articles_count": _graph_articles_count,
            "faculty_articles_displayed": len(articles),
            "faculty_articles_total": (
                FacultyPublication.objects.count() if using_faculty_data else 0
            ),
            "faculty_staff_displayed": len(staff),
            "faculty_staff_total": (
                FacultyPerson.objects.filter(is_stale=False).count() if using_faculty_data else 0
            ),
            "faculty_courses_total": 0,
        },
    )


def _fetch_faculty_publications(limit: int = 30) -> list[dict]:
    cache_key = f"faculty:pubs:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        pubs = list(
            FacultyPublication.objects.prefetch_related(
                Prefetch(
                    "authorships",
                    queryset=FacultyAuthorship.objects.order_by("position"),
                )
            ).order_by("-year", "-id")[:limit]
        )
        articles = []
        for pub in pubs:
            authors = [a.display_name for a in pub.authorships.all() if a.display_name]
            raw = pub.raw_payload if isinstance(pub.raw_payload, dict) else {}
            venue = str(raw.get("venue") or raw.get("journal") or raw.get("source") or "")
            kw_raw = raw.get("keywords") or raw.get("tags") or []
            keywords = [str(k) for k in kw_raw if k] if isinstance(kw_raw, list) else []
            articles.append(
                {
                    "title": pub.title,
                    "authors": authors,
                    "venue": venue,
                    "year": pub.year,
                    "doi_url": pub.url or "",
                    "keywords": keywords,
                    "direction": _PUB_TYPE_RU.get(pub.publication_type, pub.publication_type),
                }
            )
        if articles:
            cache.set(cache_key, articles, timeout=_FACULTY_CACHE_TTL)
        return articles
    except Exception:
        logger.warning("faculty ORM publications query failed", exc_info=True)
        return []


def _fetch_faculty_staff(limit: int = 50) -> list[dict]:
    cache_key = f"faculty:staff:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        persons = list(
            FacultyPerson.objects.filter(is_stale=False).order_by("-publications_total")[:limit]
        )
        staff = []
        for p in persons:
            position = ""
            if isinstance(p.positions, list) and p.positions:
                first = p.positions[0]
                if isinstance(first, dict):
                    position = str(first.get("position") or first.get("title") or "").strip()
            staff.append(
                {
                    "name": p.full_name,
                    "position": position or p.primary_unit,
                    "department": p.primary_unit,
                    "research_areas": list(p.interests)[:3] if p.interests else [],
                    "works_count": p.publications_total,
                    "profile_url": p.source_profile_url,
                }
            )
        if staff:
            cache.set(cache_key, staff, timeout=_FACULTY_CACHE_TTL)
        return staff
    except Exception:
        logger.warning("faculty ORM staff query failed", exc_info=True)
        return []


def _build_graph_data(articles):
    author_articles: dict[str, list[str]] = defaultdict(list)
    for article in articles:
        for author in article.get("authors", []):
            author_articles[author].append(article.get("title", ""))

    nodes = []
    author_index: dict[str, int] = {}
    for i, (author, titles) in enumerate(author_articles.items()):
        author_index[author] = i
        nodes.append(
            {
                "id": i,
                "label": author,
                "value": len(titles),
                "title": f"{author}<br/>Публикаций в выборке: {len(titles)}",
            }
        )

    edge_counts: dict[tuple[int, int], int] = defaultdict(int)
    edge_titles: dict[tuple[int, int], list[str]] = defaultdict(list)
    for article in articles:
        authors = article.get("authors", [])
        for i in range(len(authors)):
            for j in range(i + 1, len(authors)):
                a = author_index[authors[i]]
                b = author_index[authors[j]]
                key = (min(a, b), max(a, b))
                edge_counts[key] += 1
                edge_titles[key].append(article.get("title", ""))

    edges = []
    for key, weight in edge_counts.items():
        a, b = key
        tooltip_lines = "<br/>".join(
            t[:60] + ("…" if len(t) > 60 else "") for t in edge_titles[key]
        )
        edges.append(
            {
                "from": a,
                "to": b,
                "value": weight,
                "title": f"Совместных статей: {weight}<br/>{tooltip_lines}",
            }
        )

    return nodes, edges


_GRAPH_CACHE_KEY = "graph:coauthorship"
_GRAPH_CACHE_TTL = 1800


def _fetch_coauthorship_graph() -> tuple[list, list]:

    import requests as _requests

    base_url = os.getenv("GRAPH_SERVICE_URL", "").rstrip("/")
    if not base_url:
        return [], []

    cached = cache.get(_GRAPH_CACHE_KEY)
    if cached is not None:
        return cached  # type: ignore[return-value]

    try:
        resp = _requests.get(f"{base_url}/coauthorship", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        nodes: list = data.get("nodes") or []
        edges: list = data.get("edges") or []
        if nodes:
            cache.set(_GRAPH_CACHE_KEY, (nodes, edges), timeout=_GRAPH_CACHE_TTL)
        return nodes, edges
    except Exception:
        logger.warning("graph service /coauthorship fetch failed", exc_info=True)
        return [], []


def _get_sample_articles() -> list[dict]:
    return [
        {
            "title": "Методы глубокого обучения для анализа естественного языка",
            "authors": ["Иванов А.С.", "Петрова М.В.", "Сидоров К.Н."],
            "venue": "Computational Linguistics and Intellectual Technologies",
            "year": 2024,
            "doi_url": "",
            "keywords": ["NLP", "deep learning", "transformers"],
            "direction": "Статья",
        },
        {
            "title": "Рекомендательные системы на основе графовых нейронных сетей",
            "authors": ["Петрова М.В.", "Козлов Д.А.", "Новикова А.И."],
            "venue": "Journal of Intelligent Information Systems",
            "year": 2024,
            "doi_url": "",
            "keywords": ["GNN", "recommender systems", "collaborative filtering"],
            "direction": "Статья",
        },
        {
            "title": "Оптимизация распределённых вычислений в облачных средах",
            "authors": ["Иванов А.С.", "Смирнова О.В."],
            "venue": "Distributed Computing and Applications",
            "year": 2023,
            "doi_url": "",
            "keywords": ["cloud computing", "distributed systems", "optimization"],
            "direction": "Статья",
        },
        {
            "title": "Анализ временных рядов методами машинного обучения",
            "authors": ["Козлов Д.А.", "Смирнова О.В.", "Сидоров К.Н."],
            "venue": "Machine Learning and Data Analysis",
            "year": 2023,
            "doi_url": "",
            "keywords": ["time series", "LSTM", "forecasting"],
            "direction": "Статья",
        },
        {
            "title": (
                "Безопасность программного обеспечения: автоматическое обнаружение уязвимостей"
            ),
            "authors": ["Новикова А.И.", "Иванов А.С."],
            "venue": "Information Security and Cryptography",
            "year": 2024,
            "doi_url": "",
            "keywords": ["security", "vulnerability detection", "static analysis"],
            "direction": "Статья",
        },
        {
            "title": "Компьютерное зрение для задач медицинской диагностики",
            "authors": ["Петрова М.В.", "Сидоров К.Н.", "Козлов Д.А."],
            "venue": "Medical Image Analysis",
            "year": 2023,
            "doi_url": "",
            "keywords": ["computer vision", "medical imaging", "CNN"],
            "direction": "Статья",
        },
    ]


def _get_sample_staff() -> list[dict]:
    return [
        {
            "name": "Иванов Алексей Сергеевич",
            "position": "Доцент",
            "department": "Департамент программной инженерии",
            "research_areas": ["машинное обучение", "NLP", "безопасность ПО"],
            "works_count": 42,
            "profile_url": "",
        },
        {
            "name": "Петрова Мария Владимировна",
            "position": "Старший преподаватель",
            "department": "Школа анализа данных",
            "research_areas": ["рекомендательные системы", "NLP", "компьютерное зрение"],
            "works_count": 38,
            "profile_url": "",
        },
        {
            "name": "Козлов Дмитрий Андреевич",
            "position": "Доцент",
            "department": "Департамент информационных технологий",
            "research_areas": ["анализ данных", "графовые алгоритмы", "временные ряды"],
            "works_count": 31,
            "profile_url": "",
        },
        {
            "name": "Смирнова Ольга Владимировна",
            "position": "Профессор",
            "department": "Школа анализа данных",
            "research_areas": ["распределённые системы", "анализ данных"],
            "works_count": 57,
            "profile_url": "",
        },
        {
            "name": "Новикова Анастасия Игоревна",
            "position": "Преподаватель",
            "department": "Центр разработки программного обеспечения",
            "research_areas": ["безопасность ПО", "статический анализ"],
            "works_count": 19,
            "profile_url": "",
        },
        {
            "name": "Сидоров Кирилл Николаевич",
            "position": "Доцент",
            "department": "Департамент программной инженерии",
            "research_areas": ["машинное обучение", "компьютерное зрение"],
            "works_count": 28,
            "profile_url": "",
        },
    ]
