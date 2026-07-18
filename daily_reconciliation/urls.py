from django.urls import path

from . import views

app_name = "daily_reconciliation"

urlpatterns = [
    path("", views.TodayReconciliationView.as_view(), name="today"),
    path("history/", views.DailyReconciliationListView.as_view(), name="list"),
    path("<int:pk>/", views.DailyReconciliationDetailView.as_view(), name="detail"),
]
