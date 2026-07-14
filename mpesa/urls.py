from django.urls import path

from . import views

app_name = "mpesa"

urlpatterns = [
    path("", views.MpesaTransactionListView.as_view(), name="list"),
    path("transactions/<str:trans_id>/allocate/", views.TransactionAllocateView.as_view(), name="transaction_allocate"),
    path("payment-links/", views.PaymentLinkListView.as_view(), name="payment_links"),
    path("payment-links/add/", views.PaymentLinkCreateView.as_view(), name="payment_link_add"),
    path("payment-links/<int:pk>/", views.PaymentLinkDetailView.as_view(), name="payment_link_detail"),
    path("payment-links/<int:pk>/resend/", views.PaymentLinkResendView.as_view(), name="payment_link_resend"),
    path("payment-links/<int:pk>/cancel/", views.PaymentLinkCancelView.as_view(), name="payment_link_cancel"),
    path("reconciliation/", views.ReconciliationListView.as_view(), name="reconciliation"),
    path("reconciliation/<int:pk>/match/", views.ReconciliationMatchView.as_view(), name="reconciliation_match"),
]
