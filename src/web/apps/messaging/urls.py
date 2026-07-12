from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.thread_list, name="thread_list"),
    path("new/", views.thread_create, name="thread_create"),
    path("<int:pk>/", views.thread_detail, name="thread_detail"),
]
