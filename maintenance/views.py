from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DeleteView

from core.mixins import ModulePermissionRequiredMixin
from .forms import JarTypeForm, JarTypeMaterialFormSet
from .models import JarType


class ViewMaintenanceMixin(ModulePermissionRequiredMixin):
    module_name = "maintenance"
    permission_level = "view"


class EditMaintenanceMixin(ModulePermissionRequiredMixin):
    module_name = "maintenance"
    permission_level = "edit"


class JarTypeListView(ViewMaintenanceMixin, ListView):
    model = JarType
    template_name = "maintenance/jartype_list.html"
    context_object_name = "jar_types"

    def get_queryset(self):
        return JarType.objects.prefetch_related("material_usages__material")


class JarTypeFormView(EditMaintenanceMixin, View):
    template_name = "maintenance/jartype_form.html"

    def get_object(self):
        pk = self.kwargs.get("pk")
        return get_object_or_404(JarType, pk=pk) if pk else None

    def get(self, request, *args, **kwargs):
        jar_type = self.get_object()
        form = JarTypeForm(instance=jar_type)
        formset = JarTypeMaterialFormSet(instance=jar_type)
        return render(request, self.template_name, {"form": form, "formset": formset, "object": jar_type})

    def post(self, request, *args, **kwargs):
        jar_type = self.get_object()
        form = JarTypeForm(request.POST, instance=jar_type)
        formset = JarTypeMaterialFormSet(request.POST, instance=jar_type)

        if form.is_valid() and formset.is_valid():
            jar_type = form.save()
            formset.instance = jar_type
            formset.save()
            messages.success(request, "Jar type saved.")
            return redirect(reverse_lazy("maintenance:list"))

        return render(request, self.template_name, {"form": form, "formset": formset, "object": jar_type})


class JarTypeDeleteView(EditMaintenanceMixin, DeleteView):
    model = JarType
    success_url = reverse_lazy("maintenance:list")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("maintenance:list")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Jar type deleted.")
        return super().form_valid(form)
