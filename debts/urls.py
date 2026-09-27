from django.urls import path

from . import views

app_name = "debts"

urlpatterns = [
    path("", views.DebtGroupedListView.as_view(), name="grouped"),
    path("individual/", views.DebtIndividualListView.as_view(), name="individual"),
    path("cleared/", views.DebtClearedListView.as_view(), name="cleared"),
    path("sale/<int:pk>/rollback/", views.DebtRollbackClearanceView.as_view(), name="rollback_clearance"),
    path("export/excel/", views.DebtExcelExportView.as_view(), name="export_excel"),
    path("export/pdf/", views.DebtPdfExportView.as_view(), name="export_pdf"),
    path("invoice/", views.InvoicePdfView.as_view(), name="invoice"),
    path("invoice/preview/", views.InvoicePreviewView.as_view(), name="invoice_preview"),
    path("bulk-update/", views.DebtBulkUpdateStatusView.as_view(), name="bulk_update"),
    path("sale/<int:pk>/", views.DebtDetailView.as_view(), name="sale_detail"),
    path("sale/<int:pk>/pay/", views.DebtPaymentCreateView.as_view(), name="record_payment"),
    path("prepayment/", views.PrepaymentCreateView.as_view(), name="prepayment_add"),
    path("credit/", views.CustomerCreditListView.as_view(), name="credit_list"),
    path("credit/detail/", views.CustomerCreditDetailView.as_view(), name="credit_detail"),
    path("credit/<int:pk>/delete/", views.CustomerCreditDeleteView.as_view(), name="credit_delete"),
]
