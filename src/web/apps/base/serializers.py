from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserProjectInlineSerializer(serializers.Serializer):
    url = serializers.HyperlinkedIdentityField(view_name="project-detail", lookup_field="pk")
    title = serializers.CharField(read_only=True)


class UserPublicSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True)
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ["username", "id"]

    # def get_other_projects(self, obj):
    #     # request = self.context.get('request')
    #     # print(obj)
    #     user = obj
    #     my_projects = user.project_set.all()[:5]
    #     return UserProjectInlineSerializer(my_projects, many=True, context=self.context).data
