from django.urls import path

from . import views

app_name = "commissions"

urlpatterns = [
    path("", views.CommissionAccountListView.as_view(), name="list"),
    path("add/", views.CommissionAccountCreateView.as_view(), name="add"),
    path("<int:pk>/", views.CommissionAccountDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.CommissionAccountUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.CommissionAccountDeleteView.as_view(), name="delete"),
]
