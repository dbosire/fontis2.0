from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from core.mixins import ModulePermissionRequiredMixin
from .forms import LabTestForm
from .models import LabTest


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
