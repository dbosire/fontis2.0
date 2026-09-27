from django.urls import path

from . import views

app_name = "system_info"

urlpatterns = [
    path("", views.SystemInfoUpdateView.as_view(), name="edit"),
    path("health/", views.SystemHealthView.as_view(), name="health"),
    path("health/backup-now/", views.BackupNowView.as_view(), name="backup_now"),
    path("health/backups/<str:filename>/download/", views.BackupDownloadView.as_view(), name="backup_download"),
]
