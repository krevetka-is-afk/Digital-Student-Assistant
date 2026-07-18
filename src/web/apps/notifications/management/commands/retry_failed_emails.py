from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.notifications.models import Notification, NotificationEmailStatus
from apps.notifications.services import _send_email_for_notification


class Command(BaseCommand):
    help = (
        "Retry sending emails for notifications that previously failed. "
        "Useful after fixing SMTP configuration or network issues."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of notifications to retry in one run (default: 100).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print which notifications would be retried without actually sending.",
        )

    def handle(self, *args, **options):
        limit: int = options["limit"]
        dry_run: bool = options["dry_run"]

        if limit <= 0:
            raise CommandError("--limit must be a positive integer.")

        qs = (
            Notification.objects.filter(email_status=NotificationEmailStatus.FAILED)
            .select_related("recipient")
            .order_by("created_at")[:limit]
        )
        failed = list(qs)

        if not failed:
            self.stdout.write(self.style.SUCCESS("No failed notifications found."))
            return

        self.stdout.write(f"Found {len(failed)} failed notification(s) to retry.")

        if dry_run:
            for n in failed:
                self.stdout.write(
                    f"  [dry-run] id={n.pk} recipient={n.recipient} "
                    f"event={n.event_type} error={n.email_error!r}"
                )
            self.stdout.write(self.style.WARNING("Dry run — no emails sent."))
            return

        sent = 0
        still_failed = 0
        for n in failed:
            Notification.objects.filter(pk=n.pk).update(
                email_status=NotificationEmailStatus.PENDING,
                email_error="",
            )
            _send_email_for_notification(n.pk)
            n.refresh_from_db(fields=["email_status", "email_error"])
            if n.email_status == NotificationEmailStatus.SENT:
                sent += 1
                self.stdout.write(f"  ✓ id={n.pk} sent to {n.recipient}")
            else:
                still_failed += 1
                self.stdout.write(
                    self.style.ERROR(f"  ✗ id={n.pk} still failed: {n.email_error!r}")
                )

        summary = f"Done: {sent} sent, {still_failed} still failed."
        if still_failed:
            self.stdout.write(self.style.WARNING(summary))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
