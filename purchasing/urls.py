from django.urls import path

from . import views

app_name = "purchasing"

urlpatterns = [
    path("requests/", views.PurchaseRequestListView.as_view(), name="requests"),
    path("requests/add/", views.PurchaseRequestCreateView.as_view(), name="request_add"),
    path("requests/<int:pk>/", views.PurchaseRequestDetailView.as_view(), name="request_detail"),
    path("requests/<int:pk>/delete/", views.PurchaseRequestDeleteView.as_view(), name="request_delete"),
    path("requests/<int:pk>/create-order/", views.PurchaseOrderCreateFromRequestView.as_view(), name="order_from_request"),
    path("requests/<int:pk>/<str:decision>/", views.PurchaseRequestDecisionView.as_view(), name="request_decision"),

    path("orders/", views.PurchaseOrderListView.as_view(), name="orders"),
    path("orders/add/", views.PurchaseOrderCreateView.as_view(), name="order_add"),
    path("orders/<int:pk>/", views.PurchaseOrderDetailView.as_view(), name="order_detail"),
    path("orders/<int:pk>/edit/", views.PurchaseOrderUpdateView.as_view(), name="order_edit"),
    path("orders/<int:pk>/send/", views.PurchaseOrderSendView.as_view(), name="order_send"),
    path("orders/<int:pk>/receive/", views.GoodsReceiptCreateView.as_view(), name="receipt_add"),
]
