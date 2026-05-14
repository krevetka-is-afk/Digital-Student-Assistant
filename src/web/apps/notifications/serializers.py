from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "event_type",
            "title",
            "body",
            "target_type",
            "target_id",
            "created_at",
            "read_at",
            "actor",
            "recipient",
            "email_status",
            "email_sent_at",
        ]
        read_only_fields = fields


class MarkReadInputSerializer(serializers.Serializer):
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )


class UnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()


def mark_notifications_read(*, queryset, notification_ids: list[int]) -> int:
    now = timezone.now()
    return queryset.filter(pk__in=notification_ids, read_at__isnull=True).update(read_at=now)
