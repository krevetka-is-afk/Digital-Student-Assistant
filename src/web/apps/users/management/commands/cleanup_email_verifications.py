from datetime import timedelta

from apps.users.models import EmailVerificationCode
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Delete expired or consumed email verification codes and optionally "
        "prune stale pending users."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-stale-users",
            action="store_true",
            help="Delete inactive, unverified users older than --stale-user-age-days.",
        )
        parser.add_argument(
            "--stale-user-age-days",
            type=int,
            default=30,
            help=(
                "Delete inactive users whose email is still unverified and "
                "whose profile is older than N days."
            ),
        )

    def handle(self, *args, **options):
        now = timezone.now()
        deleted_codes, _ = EmailVerificationCode.objects.filter(
            Q(expires_at__lt=now) | Q(consumed_at__isnull=False),
        ).delete()
        self.stdout.write(f"Deleted email verification codes: {deleted_codes}")

        if not options["delete_stale_users"]:
            return

        stale_before = now - timedelta(days=options["stale_user_age_days"])
        stale_users = User.objects.filter(
            is_active=False,
            date_joined__lt=stale_before,
            profile__email_verified_at__isnull=True,
        )
        deleted_users = stale_users.count()
        stale_users.delete()
        self.stdout.write(f"Deleted stale unverified users: {deleted_users}")
