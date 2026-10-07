import csv

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from core.mixins import ModulePermissionRequiredMixin
from .forms import LabTestForm
from .importer import parse_upload, save_rows
from .models import LabTest

IMPORT_SESSION_KEY = "labtest_import"


class ViewWaterTestMixin(ModulePermissionRequiredMixin):
    module_name = "water_test"
    permission_level = "view"


class EditWaterTestMixin(ModulePermissionRequiredMixin):
    module_name = "water_test"
    permission_level = "edit"


class LabTestListView(ViewWaterTestMixin, ListView):
    model = LabTest
    template_name = "water_test/labtest_list.html"
    context_object_name = "tests"
    paginate_by = 30


class LabTestCreateView(EditWaterTestMixin, CreateView):
    model = LabTest
    form_class = LabTestForm
    template_name = "water_test/labtest_form.html"
    success_url = reverse_lazy("water_test:list")

    def form_valid(self, form):
        messages.success(self.request, "Test result added.")
        return super().form_valid(form)


class LabTestUpdateView(EditWaterTestMixin, UpdateView):
    model = LabTest
    form_class = LabTestForm
    template_name = "water_test/labtest_form.html"
    success_url = reverse_lazy("water_test:list")

    def form_valid(self, form):
        messages.success(self.request, "Test result updated.")
        return super().form_valid(form)


class LabTestDeleteView(EditWaterTestMixin, DeleteView):
    model = LabTest
    success_url = reverse_lazy("water_test:list")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("water_test:list")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Test result deleted.")
        return super().form_valid(form)


class LabTestImportView(EditWaterTestMixin, View):
    """Step 1 of bulk-loading genuine results from a spreadsheet: pick the file. It is
    parsed and checked, then held in the session for the preview page — nothing is
    written to lab_test until the user confirms there."""

    template_name = "water_test/labtest_import.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            messages.error(request, "Choose a file to upload.")
            return redirect("water_test:import")
        try:
            result = parse_upload(upload)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("water_test:import")
        result["filename"] = upload.name
        request.session[IMPORT_SESSION_KEY] = result
        return redirect("water_test:import_preview")


class LabTestImportPreviewView(EditWaterTestMixin, View):
    template_name = "water_test/labtest_import_preview.html"

    def get(self, request):
        result = request.session.get(IMPORT_SESSION_KEY)
        if not result:
            return redirect("water_test:import")
        return render(request, self.template_name, {
            "result": result,
            "sample_rows": result["rows"][:20],
            "errors": result["errors"][:200],
            "more_errors": max(len(result["errors"]) - 200, 0),
        })

    def post(self, request):
        result = request.session.pop(IMPORT_SESSION_KEY, None)
        if not result:
            return redirect("water_test:import")
        if request.POST.get("action") != "confirm":
            messages.info(request, "Import cancelled — nothing was saved.")
            return redirect("water_test:import")
        created, skipped = save_rows(result["rows"])
        text = f"Imported {created} test result{'s' if created != 1 else ''}."
        if skipped:
            text += f" {skipped} already existed and were left unchanged."
        messages.success(request, text)
        return redirect("water_test:list")


class LabTestImportTemplateView(EditWaterTestMixin, View):
    """Header-only CSV so the columns match what the importer expects."""

    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="lab_test_import_template.csv"'
        csv.writer(response).writerow(["Date", "Sample", "Technician", "TDS", "EC", "pH", "Salinity", "Temp"])
        return response
