from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("reports/sales/", views.SalesReportView.as_view(), name="sales_report"),
]
