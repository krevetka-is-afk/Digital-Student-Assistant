from rest_framework import generics, permissions

from .models import OutboxEvent
from .serializers import OutboxEventSerializer


class OutboxEventListAPIView(generics.ListAPIView):
    serializer_class = OutboxEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = OutboxEvent.objects.all()
        event_type = self.request.query_params.get("event_type")
        since_id = self.request.query_params.get("since_id")
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        if since_id and since_id.isdigit():
            queryset = queryset.filter(id__gt=int(since_id))
        return queryset
