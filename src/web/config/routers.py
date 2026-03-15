from apps.projects.viewsets import ProjectGenericViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register("projects", ProjectGenericViewSet, basename="projects")
# print(router.urls)
urlpatterns = router.urls
