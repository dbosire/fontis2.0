from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("", views.SaleListView.as_view(), name="list"),
    path("add/", views.SaleFormView.as_view(), name="add"),
    path("<int:pk>/edit/", views.SaleFormView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.SaleDeleteView.as_view(), name="delete"),
    path("bulk-update/", views.SaleBulkUpdateStatusView.as_view(), name="bulk_update"),
]
