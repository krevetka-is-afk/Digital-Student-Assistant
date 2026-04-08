from django.db import models


class ImportRun(models.Model):
    source = models.CharField(max_length=50, default="xlsx")
    source_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, default="pending", db_index=True)
    imported_by_id = models.PositiveIntegerField(null=True, blank=True)
    stats = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"ImportRun #{self.pk} ({self.status})"
