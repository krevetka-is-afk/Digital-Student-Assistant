from apps.products.viewsets import ProductGenericViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register("products", ProductGenericViewSet, basename="products")
# print(router.urls)
urlpatterns = router.urls
