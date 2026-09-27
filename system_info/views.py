import time

import django
from django.conf import settings
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView

from core.mixins import ModulePermissionRequiredMixin, SuperuserRequiredMixin
from . import services_health
from .forms import SystemInfoForm
from .models import ScheduledTaskRun
from .services import get_setting, get_settings_dict, set_setting


class EditSystemInfoMixin(ModulePermissionRequiredMixin):
    module_name = "system_info"
    permission_level = "edit"


class SystemInfoUpdateView(EditSystemInfoMixin, FormView):
    form_class = SystemInfoForm
    template_name = "system_info/system_info_form.html"
    success_url = reverse_lazy("system_info:edit")

    def get_initial(self):
        settings_dict = get_settings_dict()
        return {"name": settings_dict.get("name", ""), "short_name": settings_dict.get("short_name", "")}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["current_logo"] = get_setting("logo")
        ctx["current_cover"] = get_setting("cover")
        return ctx

    def form_valid(self, form):
        set_setting("name", form.cleaned_data["name"])
        set_setting("short_name", form.cleaned_data["short_name"])

        uploads_dir = settings.MEDIA_ROOT / "uploads"
        storage = FileSystemStorage(location=str(uploads_dir), base_url=f"{settings.MEDIA_URL}uploads/")

        for field_name in ("logo", "cover"):
            uploaded = form.cleaned_data.get(field_name)
            if uploaded:
                filename = f"{int(time.time())}_{uploaded.name}"
                storage.save(filename, uploaded)
                set_setting(field_name, f"uploads/{filename}")

        messages.success(self.request, "Settings updated.")
        return super().form_valid(form)


class SystemHealthView(SuperuserRequiredMixin, View):
    """Superuser-only, not just system_info "view" — this page surfaces disk usage,
    M-Pesa configuration status, and a listing of full-database backups, none of
    which an ordinary settings-editor role should see just by having access to
    branding settings."""

    template_name = "system_info/system_health.html"

    def get(self, request):
        ctx = {
            "django_version": django.get_version(),
            "checks": services_health.all_checks(),
            "operations": services_health.operations(),
            "disk": services_health.disk_usage(),
            "runs": services_health.scheduler_runs(),
            "backups": services_health.list_backups(),
        }
        return render(request, self.template_name, ctx)


class BackupNowView(SuperuserRequiredMixin, View):
    """Runs backup_db synchronously — the dumps here are small (KBs, see the
    Backups table), so a request/response round trip is fine; no task queue exists
    in this project to defer it to."""

    def post(self, request):
        try:
            call_command("backup_db", source=ScheduledTaskRun.MANUAL)
            messages.success(request, "Backup complete.")
        except Exception as exc:
            messages.error(request, f"Backup failed: {exc}")
        return redirect(reverse("system_info:health"))


class BackupDownloadView(SuperuserRequiredMixin, View):
    """`filename` is matched against the actual backups/ listing rather than
    trusted as a path — no traversal, no serving anything outside that directory."""

    def get(self, request, filename):
        if filename not in {b["name"] for b in services_health.list_backups(limit=1000)}:
            raise Http404
        filepath = services_health.BACKUP_DIR / filename
        return FileResponse(open(filepath, "rb"), as_attachment=True, filename=filename)
