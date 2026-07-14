from django.urls import path

from . import views

app_name = "contacts"

urlpatterns = [
    path("", views.ContactListView.as_view(), name="list"),
    path("add/", views.ContactCreateView.as_view(), name="add"),
    path("<int:pk>/edit/", views.ContactUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ContactDeleteView.as_view(), name="delete"),
]
