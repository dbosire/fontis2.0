from django.urls import path

from . import views

app_name = "water_test"

urlpatterns = [
    path("", views.LabTestListView.as_view(), name="list"),
    path("add/", views.LabTestCreateView.as_view(), name="add"),
    path("<int:pk>/edit/", views.LabTestUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.LabTestDeleteView.as_view(), name="delete"),
]
