from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.thread_list, name="thread_list"),
    path("open/", views.thread_open, name="thread_open"),
    path("new/", views.thread_create, name="thread_create"),
    path("<int:pk>/", views.thread_detail, name="thread_detail"),
    path("<int:pk>/messages/", views.thread_messages_partial, name="thread_messages_partial"),
]
