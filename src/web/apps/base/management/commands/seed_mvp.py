import os

from apps.applications.models import Application, ApplicationStatus
from apps.projects.models import Project, ProjectSourceType, ProjectStatus
from apps.users.models import UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Seed minimal MVP domain data (users, projects, applications)."

    @staticmethod
    def _set_seed_password(user):
        """
        Optional local-only password for seeded users.
        If env var is absent, set an unusable password to avoid hardcoded secrets.
        """
        seed_password = os.getenv("DSA_SEED_USER_PASSWORD", "").strip()
        if seed_password:
            user.set_password(seed_password)
        else:
            user.set_unusable_password()
        user.save(update_fields=["password"])

    def handle(self, *args, **options):
        owner, _ = User.objects.get_or_create(
            username="mvp_owner",
            defaults={"email": "owner@example.com"},
        )
        self._set_seed_password(owner)

        applicant, _ = User.objects.get_or_create(
            username="mvp_student",
            defaults={"email": "student@example.com"},
        )
        self._set_seed_password(applicant)

        UserProfile.objects.get_or_create(
            user=owner,
            defaults={"role": UserRole.CUSTOMER, "interests": ["ai", "education"]},
        )
        UserProfile.objects.get_or_create(
            user=applicant,
            defaults={"role": UserRole.STUDENT, "interests": ["llm", "ml"]},
        )

        project, _ = Project.objects.get_or_create(
            title="MVP demo project",
            defaults={
                "description": "Demo project created by seed_mvp command.",
                "owner": owner,
                "status": ProjectStatus.PUBLISHED,
                "source_type": ProjectSourceType.MANUAL,
                "tech_tags": ["python", "django"],
                "extra_data": {"seeded": True},
            },
        )

        Application.objects.get_or_create(
            project=project,
            applicant=applicant,
            defaults={
                "status": ApplicationStatus.SUBMITTED,
                "motivation": "I want to build and validate the MVP.",
            },
        )

        self.stdout.write(self.style.SUCCESS("MVP seed data is ready."))
        self.stdout.write(
            "Seed users have unusable passwords by default. "
            "Set DSA_SEED_USER_PASSWORD to enable local login for seeded users."
        )
