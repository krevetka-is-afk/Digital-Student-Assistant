from __future__ import annotations

from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import (
    MarkReadInputSerializer,
    NotificationSerializer,
    UnreadCountSerializer,
    mark_notifications_read,
)


class NotificationListAPIView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.select_related("actor", "recipient").filter(
            recipient=self.request.user
        )
        unread = (self.request.query_params.get("unread") or "").strip().lower()
        if unread in {"1", "true", "yes", "on"}:
            qs = qs.filter(read_at__isnull=True)
        return qs.order_by("-created_at", "-id")


class NotificationMarkReadAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = MarkReadInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        qs = Notification.objects.filter(recipient=request.user)
        updated = mark_notifications_read(
            queryset=qs,
            notification_ids=payload.validated_data["notification_ids"],
        )
        return Response({"marked_read": updated})


class NotificationUnreadCountAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        unread_count = Notification.objects.filter(
            recipient=request.user, read_at__isnull=True
        ).count()
        serializer = UnreadCountSerializer({"unread_count": unread_count})
        return Response(serializer.data)
