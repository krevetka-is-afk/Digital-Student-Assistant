from rest_framework import serializers

from .models import ImportRun


class ImportRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportRun
        fields = [
            "id",
            "source",
            "source_name",
            "status",
            "imported_by_id",
            "stats",
            "error_message",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields
