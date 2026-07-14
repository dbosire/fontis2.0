from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("materials/", views.MaterialListView.as_view(), name="materials"),
    path("materials/add/", views.MaterialCreateView.as_view(), name="material_add"),
    path("materials/<int:pk>/edit/", views.MaterialUpdateView.as_view(), name="material_edit"),
    path("materials/<int:pk>/delete/", views.MaterialDeleteView.as_view(), name="material_delete"),
    path("reorder-levels/", views.ReorderLevelsView.as_view(), name="reorder_levels"),
    path("suppliers/", views.SupplierListView.as_view(), name="suppliers"),
    path("suppliers/add/", views.SupplierCreateView.as_view(), name="supplier_add"),
    path("suppliers/<int:pk>/edit/", views.SupplierUpdateView.as_view(), name="supplier_edit"),
    path("suppliers/<int:pk>/delete/", views.SupplierDeleteView.as_view(), name="supplier_delete"),
    path("purchases/", views.PurchaseListView.as_view(), name="purchases"),
    path("purchases/add/", views.PurchaseCreateView.as_view(), name="purchase_add"),
    path("movements/", views.StockMovementListView.as_view(), name="movements"),
    path("expiry-dates/", views.ExpiryDatesView.as_view(), name="expiry_dates"),
]
