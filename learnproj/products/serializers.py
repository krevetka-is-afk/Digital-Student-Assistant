from base.serializers import UserPublicSerializer
from rest_framework import serializers
from rest_framework.reverse import reverse

from . import validators
from .models import Product


class ProductInlineSerializer(serializers.Serializer):
    url = serializers.HyperlinkedIdentityField(view_name="product-detail", lookup_field="pk")
    title = serializers.CharField(read_only=True)


class PrimaryProductSerializer(serializers.ModelSerializer):
    owner = UserPublicSerializer(source="user", read_only=True)
    related_products = ProductInlineSerializer(
        source="user.product_set.all", read_only=True, many=True
    )
    my_discount = serializers.SerializerMethodField(read_only=True)
    my_user_data = serializers.SerializerMethodField(read_only=True)
    url = serializers.SerializerMethodField(read_only=True)
    edit_url = serializers.SerializerMethodField(read_only=True)
    url_ = serializers.HyperlinkedIdentityField(view_name="product-detail", lookup_field="pk")

    # email = serializers.EmailField(write_only=True)
    title = serializers.CharField(
        validators=[validators.unique_product_title, validators.validate_title_no_hello]
    )

    # name = serializers.CharField(source='title', read_only=True)
    # email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Product
        fields = [
            "owner",
            # "email",
            "url",
            "url_",
            "edit_url",
            "pk",
            "title",
            # "name",
            "content",
            "price",
            "sale_price",
            "get_discount",
            "my_discount",
            "my_user_data",
            "related_products",
        ]

    def get_my_user_data(self, obj):
        return {"username": obj.user.username}

    # def validate_title(self, value):
    #     request = self.context.get("request")
    #     user = request.user
    #     qs = Product.objects.filter(user=user, title__iexact=value)  # title__exact
    #     if qs.exists():
    #         raise serializers.ValidationError(f"{value} is already a product name.")
    #     return value

    # def create(self, validated_data):
    #     # return Product.objects.create(**validated_data)
    #     # email = validated_data.pop('email')
    #     obj = super().create(validated_data)
    #     # print(email, obj)
    #     return obj

    # def update(self, instance, validated_data):  # default method
    #     instance.title = validated_data.get("title")
    #     return instance

    def get_url(self, obj):
        # return f'/base/products/{obj.pk}/'
        request = self.context.get("request")

        if request is None:
            return None

        return reverse("product-detail", kwargs={"pk": obj.pk}, request=request)

    def get_edit_url(self, obj):
        # return f'/base/products/{obj.pk}/'
        request = self.context.get("request")

        if request is None:
            return None

        return reverse("product-edit", kwargs={"pk": obj.pk}, request=request)

    def get_my_discount(self, obj):
        # obj.user -> user.username
        if not hasattr(obj, "id"):
            return None
        if not isinstance(obj, Product):
            return None

        try:
            return obj.get_discount()
        except BaseException:
            return None


class SecondaryProductSerializer(serializers.ModelSerializer):
    my_discount = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = ["title", "content", "price", "sale_price", "get_discount", "my_discount"]

    def get_my_discount(self, obj):
        print(obj.id)
        # obj.user -> user.username
        return obj.get_discount()
