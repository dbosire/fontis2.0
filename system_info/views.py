import time

from django.conf import settings
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.urls import reverse_lazy
from django.views.generic import FormView

from core.mixins import ModulePermissionRequiredMixin
from .forms import SystemInfoForm
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
