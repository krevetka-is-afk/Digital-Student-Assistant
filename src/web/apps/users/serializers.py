from rest_framework import serializers

from .models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "role",
            "bio",
            "interests",
            "favorite_project_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "username", "email", "full_name", "created_at", "updated_at"]

    def get_full_name(self, obj):
        return obj.user.get_full_name()
