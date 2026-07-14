from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from core.mixins import ModulePermissionRequiredMixin
from .forms import PurchaseForm, RawMaterialForm, SupplierForm
from .models import Purchase, RawMaterial, StockMovement, Supplier
from .services import record_stock_movement


class ViewInventoryMixin(ModulePermissionRequiredMixin):
    module_name = "inventory"
    permission_level = "view"


class EditInventoryMixin(ModulePermissionRequiredMixin):
    module_name = "inventory"
    permission_level = "edit"


# See reports/views.py for why this can't just be timezone.localdate() (USE_TZ=False).
def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


class MaterialListView(ViewInventoryMixin, ListView):
    model = RawMaterial
    template_name = "inventory/material_list.html"
    context_object_name = "materials"

    def get_queryset(self):
        qs = RawMaterial.objects.select_related("default_supplier")
        category = self.request.GET.get("category", "")
        if category:
            qs = qs.filter(category=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["category_choices"] = RawMaterial.CATEGORY_CHOICES
        ctx["selected_category"] = self.request.GET.get("category", "")
        return ctx


class MaterialCreateView(EditInventoryMixin, CreateView):
    model = RawMaterial
    form_class = RawMaterialForm
    template_name = "inventory/material_form.html"
    success_url = reverse_lazy("inventory:materials")

    def form_valid(self, form):
        messages.success(self.request, "Raw material added.")
        return super().form_valid(form)


class MaterialUpdateView(EditInventoryMixin, UpdateView):
    model = RawMaterial
    form_class = RawMaterialForm
    template_name = "inventory/material_form.html"
    success_url = reverse_lazy("inventory:materials")

    def form_valid(self, form):
        messages.success(self.request, "Raw material updated.")
        return super().form_valid(form)


class MaterialDeleteView(EditInventoryMixin, DeleteView):
    model = RawMaterial
    success_url = reverse_lazy("inventory:materials")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("inventory:materials")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Raw material deleted.")
        return super().form_valid(form)


class ReorderLevelsView(ViewInventoryMixin, ListView):
    template_name = "inventory/reorder_levels.html"
    context_object_name = "materials"

    def get_queryset(self):
        return [m for m in RawMaterial.objects.select_related("default_supplier").all() if m.is_low_stock]


class SupplierListView(ViewInventoryMixin, ListView):
    model = Supplier
    template_name = "inventory/supplier_list.html"
    context_object_name = "suppliers"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = SupplierForm()
        return ctx


class SupplierCreateView(EditInventoryMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "inventory/supplier_list.html"
    success_url = reverse_lazy("inventory:suppliers")

    def form_valid(self, form):
        messages.success(self.request, "Supplier saved.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["suppliers"] = Supplier.objects.all()
        return ctx


class SupplierUpdateView(EditInventoryMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "inventory/supplier_form.html"
    success_url = reverse_lazy("inventory:suppliers")

    def form_valid(self, form):
        messages.success(self.request, "Supplier updated.")
        return super().form_valid(form)


class SupplierDeleteView(EditInventoryMixin, DeleteView):
    model = Supplier
    success_url = reverse_lazy("inventory:suppliers")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("inventory:suppliers")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Supplier deleted.")
        return super().form_valid(form)


class PurchaseListView(ViewInventoryMixin, ListView):
    model = Purchase
    template_name = "inventory/purchase_list.html"
    context_object_name = "purchases"
    paginate_by = 30

    def get_queryset(self):
        return Purchase.objects.select_related("material", "supplier")


class PurchaseCreateView(EditInventoryMixin, CreateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = "inventory/purchase_form.html"
    success_url = reverse_lazy("inventory:purchases")

    def form_valid(self, form):
        response = super().form_valid(form)
        purchase = self.object
        record_stock_movement(
            purchase.material,
            purchase.quantity,
            StockMovement.PURCHASE,
            reference=f"Purchase #{purchase.pk}",
            user=self.request.user,
        )
        messages.success(
            self.request,
            f"Purchase recorded — {purchase.material.name} stock increased by {purchase.quantity:g}.",
        )
        return response


class StockMovementListView(ViewInventoryMixin, ListView):
    model = StockMovement
    template_name = "inventory/movement_list.html"
    context_object_name = "movements"
    paginate_by = 50

    def get_queryset(self):
        qs = StockMovement.objects.select_related("material", "created_by")
        material_id = self.request.GET.get("material", "")
        if material_id:
            qs = qs.filter(material_id=material_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["materials"] = RawMaterial.objects.all()
        ctx["selected_material"] = self.request.GET.get("material", "")
        return ctx


class ExpiryDatesView(ViewInventoryMixin, ListView):
    template_name = "inventory/expiry_dates.html"
    context_object_name = "purchases"

    def get_queryset(self):
        return (
            Purchase.objects.select_related("material", "supplier")
            .filter(expiry_date__isnull=False)
            .order_by("expiry_date")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = _today()
        ctx["today"] = today
        ctx["soon_cutoff"] = today + timedelta(days=30)
        return ctx
