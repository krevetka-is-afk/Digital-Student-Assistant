"""Management command: sync faculty persons and publications to Neo4j via graph service.

Usage:
    python manage.py sync_faculty_to_graph
    python manage.py sync_faculty_to_graph --dry-run
    python manage.py sync_faculty_to_graph --graph-url http://localhost:8002

Strategy
--------
We load ALL co-authors for every publication that has at least one FacultyPerson
author (person_id IS NOT NULL). Co-authors who are not in FacultyPerson get a
synthetic source_key derived from their display_name. This ensures that all
co-authorship pairs — including those with external / unsynced authors — appear
as edges in the Neo4j graph.
"""

from __future__ import annotations

import hashlib
import logging
import os

import requests
from apps.faculty.models import FacultyAuthorship, FacultyPerson, FacultyPublication
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Prefetch

logger = logging.getLogger(__name__)

_PUB_BATCH_SIZE = 200  # publications per HTTP request


def _virtual_source_key(display_name: str) -> str:
    """Stable, short key for a co-author that has no FacultyPerson record."""
    digest = hashlib.md5(display_name.strip().lower().encode()).hexdigest()[:12]
    return f"dname:{digest}"


class Command(BaseCommand):
    help = (
        "Sync FacultyPerson / FacultyPublication data from PostgreSQL into Neo4j "
        "via graph service. Includes virtual nodes for co-authors not in FacultyPerson."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--graph-url",
            default="",
            help="Override GRAPH_SERVICE_URL env var (e.g. http://localhost:8002).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print counts and exit without sending data.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=60,
            help="HTTP timeout in seconds for each batch request (default: 60).",
        )

    def handle(self, *args, **options):
        base_url = (options["graph_url"] or os.getenv("GRAPH_SERVICE_URL", "")).rstrip("/")
        if not base_url:
            raise CommandError(
                "GRAPH_SERVICE_URL is not configured. Set the env variable or pass --graph-url."
            )

        endpoint = f"{base_url}/faculty/import"
        dry_run = options["dry_run"]
        timeout = options["timeout"]

        # ── 1. Load known persons ────────────────────────────────────────────
        real_persons = list(
            FacultyPerson.objects.filter(is_stale=False).values(
                "source_key", "full_name", "primary_unit", "publications_total"
            )
        )
        known_source_keys = {p["source_key"] for p in real_persons}
        self.stdout.write(f"Known persons (not stale): {len(real_persons)}")

        # ── 2. Load publications with ALL their authorships ──────────────────
        # Filter: at least one authorship must link to a real FacultyPerson.
        # But prefetch ALL authorships (including display_name-only ones).
        pubs_qs = (
            FacultyPublication.objects.filter(authorships__person__isnull=False)
            .distinct()
            .prefetch_related(
                Prefetch(
                    "authorships",
                    queryset=FacultyAuthorship.objects.select_related("person").order_by(
                        "position"
                    ),
                )
            )
        )

        virtual_persons: dict[str, dict] = {}  # source_key → person dict
        publications: list[dict] = []

        for pub in pubs_qs:
            authors = []
            for a in pub.authorships.all():
                if a.person_id is not None:
                    # Real FacultyPerson
                    source_key = a.person.source_key
                else:
                    # Virtual node — derive a stable key from the display name
                    if not a.display_name:
                        continue
                    source_key = _virtual_source_key(a.display_name)
                    if source_key not in known_source_keys and source_key not in virtual_persons:
                        virtual_persons[source_key] = {
                            "source_key": source_key,
                            "full_name": a.display_name,
                            "primary_unit": "",
                            "publications_total": 0,
                        }

                authors.append(
                    {
                        "person_source_key": source_key,
                        "display_name": a.display_name,
                        "position": a.position,
                    }
                )

            if len(authors) >= 2:  # only keep publications with 2+ authors
                publications.append(
                    {
                        "source_publication_id": pub.source_publication_id,
                        "title": pub.title,
                        "year": pub.year,
                        "authors": authors,
                    }
                )

        all_persons = real_persons + list(virtual_persons.values())
        total_authorships = sum(len(p["authors"]) for p in publications)

        self.stdout.write(
            f"Virtual co-author nodes:          {len(virtual_persons)}\n"
            f"Total persons to write:           {len(all_persons)}\n"
            f"Publications (≥2 authors):         {len(publications)}\n"
            f"Authorship rows:                  {total_authorships}"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — nothing sent."))
            return

        # ── 3. Send in batches ───────────────────────────────────────────────
        totals = {"persons_written": 0, "publications_written": 0, "authorships_written": 0}

        batches = [
            publications[i : i + _PUB_BATCH_SIZE]
            for i in range(0, max(1, len(publications)), _PUB_BATCH_SIZE)
        ]

        for batch_idx, pub_batch in enumerate(batches):
            payload = {
                "persons": all_persons if batch_idx == 0 else [],
                "publications": pub_batch,
            }
            try:
                resp = requests.post(endpoint, json=payload, timeout=timeout)
                resp.raise_for_status()
            except requests.RequestException as exc:
                raise CommandError(f"Request to {endpoint} failed: {exc}") from exc

            data = resp.json()
            if batch_idx == 0:
                totals["persons_written"] = int(data.get("persons_written", 0))
            totals["publications_written"] += int(data.get("publications_written", 0))
            totals["authorships_written"] += int(data.get("authorships_written", 0))

            self.stdout.write(
                f"  batch {batch_idx + 1}/{len(batches)}: "
                f"pubs={data.get('publications_written')} "
                f"authorships={data.get('authorships_written')}"
            )

        # Edge case: no publications — still push persons
        if not publications:
            try:
                resp = requests.post(
                    endpoint,
                    json={"persons": all_persons, "publications": []},
                    timeout=timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                totals["persons_written"] = int(data.get("persons_written", 0))
            except requests.RequestException as exc:
                raise CommandError(f"Request to {endpoint} failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. persons={totals['persons_written']} "
                f"(real={len(real_persons)} virtual={len(virtual_persons)}) "
                f"publications={totals['publications_written']} "
                f"authorships={totals['authorships_written']}"
            )
        )
