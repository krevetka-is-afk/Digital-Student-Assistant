from typing import cast

from django.db import models


class DeadlineAudience(models.TextChoices):
    STUDENT = "student", "Student"
    CUSTOMER = "customer", "Customer"
    CPPRP = "cpprp", "CPPRP"
    GLOBAL = "global", "Global"


class PlatformDeadline(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=255)
    audience = models.CharField(
        max_length=20,
        choices=DeadlineAudience.choices,
        default=DeadlineAudience.GLOBAL,
    )
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ends_at", "title"]

    def __str__(self) -> str:
        return cast(str, self.title)


class DocumentTemplate(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=255)
    audience = models.CharField(
        max_length=20,
        choices=DeadlineAudience.choices,
        default=DeadlineAudience.GLOBAL,
    )
    url = models.URLField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return cast(str, self.title)
