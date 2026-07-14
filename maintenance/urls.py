from django.urls import path

from . import views

app_name = "maintenance"

urlpatterns = [
    path("", views.JarTypeListView.as_view(), name="list"),
    path("add/", views.JarTypeFormView.as_view(), name="add"),
    path("<int:pk>/edit/", views.JarTypeFormView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.JarTypeDeleteView.as_view(), name="delete"),
]
