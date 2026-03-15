from django.urls import path

from . import views

urlpatterns = [
    path("", views.getData, name="legacy-api-root"),
    path("add/", views.addItem, name="legacy-api-add"),
]
