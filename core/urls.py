from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("activity-log/", views.ActivityLogListView.as_view(), name="activity_log"),
]
