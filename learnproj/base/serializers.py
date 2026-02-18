from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserProductInlineSerializer(serializers.Serializer):
    url = serializers.HyperlinkedIdentityField(view_name="product-detail", lookup_field="pk")
    title = serializers.CharField(read_only=True)


class UserPublicSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True)
    this_is_not_real = serializers.CharField(read_only=True)
    id = serializers.IntegerField(read_only=True)
    # other_products = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ["username", "this_is_not_real", "id"]

    # def get_other_products(self, obj):
    #     # request = self.context.get('request')
    #     # print(obj)
    #     user = obj
    #     my_products = user.product_set.all()[:5]
    #     return UserProductInlineSerializer(my_products, many=True, context=self.context).data
