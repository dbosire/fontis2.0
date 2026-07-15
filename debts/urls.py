from django.urls import path

from . import views

app_name = "debts"

urlpatterns = [
    path("", views.DebtGroupedListView.as_view(), name="grouped"),
    path("individual/", views.DebtIndividualListView.as_view(), name="individual"),
    path("export/excel/", views.DebtExcelExportView.as_view(), name="export_excel"),
    path("export/pdf/", views.DebtPdfExportView.as_view(), name="export_pdf"),
    path("invoice/", views.InvoicePdfView.as_view(), name="invoice"),
    path("invoice/preview/", views.InvoicePreviewView.as_view(), name="invoice_preview"),
    path("bulk-update/", views.DebtBulkUpdateStatusView.as_view(), name="bulk_update"),
    path("sale/<int:pk>/", views.DebtDetailView.as_view(), name="sale_detail"),
    path("sale/<int:pk>/pay/", views.DebtPaymentCreateView.as_view(), name="record_payment"),
]
