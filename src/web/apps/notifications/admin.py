from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recipient",
        "event_type",
        "title",
        "target_type",
        "target_id",
        "created_at",
        "read_at",
        "email_status",
    )
    list_filter = ("event_type", "target_type", "email_status", "read_at")
    search_fields = ("title", "body", "target_id", "dedupe_key")
    raw_id_fields = ("recipient", "actor")
