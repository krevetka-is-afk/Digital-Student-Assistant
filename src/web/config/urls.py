"""
URL configuration for web project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from apps.base.views import health_custom, home_page
from apps.frontend import views as frontend_views
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

handler404 = frontend_views.error_404
handler500 = frontend_views.error_500

urlpatterns = [
    path("", home_page, name="home"),
    path("", include("apps.frontend.urls", namespace="frontend")),
    path("health/", health_custom, name="health-root"),
    path("admin/", admin.site.urls),
    path("api/", include("config.api_root_urls")),
    path("base/search", include("apps.search.urls")),
    path("base/", include("apps.base.urls")),
    path("base/projects/", include("apps.projects.urls")),
    path("base/v2/", include("config.routers")),
]

if settings.DEBUG:
    urlpatterns += [
        path("__debug__/", include("debug_toolbar.urls")),
    ]
