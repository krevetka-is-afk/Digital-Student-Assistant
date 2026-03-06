from apps.projects.viewsets import ProductGenericViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register("projects", ProductGenericViewSet, basename="projects")
# print(router.urls)
urlpatterns = router.urls
