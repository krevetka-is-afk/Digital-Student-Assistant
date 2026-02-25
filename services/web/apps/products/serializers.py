from apps.base.serializers import UserPublicSerializer
from rest_framework import serializers
from rest_framework.reverse import reverse

from . import validators
from .models import Product


class ProductInlineSerializer(serializers.Serializer):
    url = serializers.HyperlinkedIdentityField(view_name="product-detail", lookup_field="pk")
    title = serializers.CharField(read_only=True)


class PrimaryProductSerializer(serializers.ModelSerializer):
    owner = UserPublicSerializer(source="user", read_only=True)
    edit_url = serializers.SerializerMethodField(read_only=True)
    url = serializers.HyperlinkedIdentityField(view_name="product-detail", lookup_field="pk")

    title = serializers.CharField(
        validators=[validators.unique_product_title, validators.validate_title_no_hello]
    )

    class Meta:
        model = Product
        fields = [
            "owner",
            "url",
            "edit_url",
            "pk",
            "title",
            "content",
            "price",
            "sale_price",
            "public",
        ]

    def get_edit_url(self, obj):
        # return f'/base/products/{obj.pk}/'
        request = self.context.get("request")

        if request is None:
            return None

        return reverse("product-edit", kwargs={"pk": obj.pk}, request=request)


class SecondaryProductSerializer(serializers.ModelSerializer):
    my_discount = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = ["title", "content", "price", "sale_price", "get_discount", "my_discount"]

    def get_my_discount(self, obj):
        print(obj.id)
        # obj.user -> user.username
        return obj.get_discount()
