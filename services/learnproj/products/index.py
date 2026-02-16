from algoliasearch_django import AlgoliaIndex
from algoliasearch_django.decorators import register

from .models import Product


@register(Product)
class ProductIndex(AlgoliaIndex):
    should_index = "is_public"
    fields = [
        "title",
        "content",
        "price",
        "public",
        # "user" # have a problem with serializer
    ]
    tags = "get_tags_list"


# admin.site.register(Product, ProductModelAdmin)
