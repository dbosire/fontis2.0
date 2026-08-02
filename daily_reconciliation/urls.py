from django.urls import path

from . import views

app_name = "daily_reconciliation"

urlpatterns = [
    path("", views.ReconciliationEntryView.as_view(), name="today"),
    path("history/", views.DailyReconciliationListView.as_view(), name="list"),
    path("<int:pk>/", views.DailyReconciliationDetailView.as_view(), name="detail"),
    path("<int:pk>/allocate-deposit/", views.CashDepositAllocateView.as_view(), name="allocate_deposit"),
    path("<int:pk>/search-deposit/", views.CashDepositSearchView.as_view(), name="search_deposit"),
]
