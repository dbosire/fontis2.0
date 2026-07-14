from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from core.mixins import ModulePermissionRequiredMixin

from .forms import (
    GoodsReceiptForm, PurchaseOrderForm, PurchaseOrderFromRequestForm, PurchaseOrderLineFormSet,
    PurchaseRequestForm, PurchaseRequestLineFormSet, PurchaseRequestRejectForm,
)
from .models import GoodsReceipt, GoodsReceiptLine, PurchaseOrder, PurchaseOrderLine, PurchaseRequest
from .services import create_purchase_order_from_request, decide_purchase_request, receive_goods


class ViewPurchasingMixin(ModulePermissionRequiredMixin):
    module_name = "purchasing"
    permission_level = "view"


class EditPurchasingMixin(ModulePermissionRequiredMixin):
    module_name = "purchasing"
    permission_level = "edit"


# See reports/views.py for why this can't just be timezone.localdate() (USE_TZ=False).
def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


# ---------------------------------------------------------------------------
# Purchase Requests
# ---------------------------------------------------------------------------

class PurchaseRequestListView(ViewPurchasingMixin, ListView):
    model = PurchaseRequest
    template_name = "purchasing/request_list.html"
    context_object_name = "requests"
    paginate_by = 30

    def get_queryset(self):
        qs = PurchaseRequest.objects.select_related("requested_by", "department")
        status = self.request.GET.get("status", "")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = PurchaseRequest.STATUS_CHOICES
        ctx["selected_status"] = self.request.GET.get("status", "")
        return ctx


class PurchaseRequestCreateView(EditPurchasingMixin, View):
    template_name = "purchasing/request_form.html"

    def get(self, request):
        form = PurchaseRequestForm()
        formset = PurchaseRequestLineFormSet()
        return render(request, self.template_name, {"form": form, "formset": formset})

    def post(self, request):
        form = PurchaseRequestForm(request.POST)
        formset = PurchaseRequestLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            pr = form.save(commit=False)
            pr.requested_by = getattr(request.user, "employee", None)
            pr.status = PurchaseRequest.PENDING
            pr.save()
            formset.instance = pr
            formset.save()
            messages.success(request, f"{pr.reference} submitted for approval.")
            return redirect(reverse("purchasing:request_detail", args=[pr.pk]))
        return render(request, self.template_name, {"form": form, "formset": formset})


class PurchaseRequestDetailView(ViewPurchasingMixin, View):
    template_name = "purchasing/request_detail.html"

    def get(self, request, pk):
        pr = get_object_or_404(PurchaseRequest.objects.select_related("requested_by", "department"), pk=pk)
        ctx = {
            "pr": pr,
            "reject_form": PurchaseRequestRejectForm(),
            "po_form": PurchaseOrderFromRequestForm(initial={"order_date": _today()}),
        }
        return render(request, self.template_name, ctx)


class PurchaseRequestDecisionView(EditPurchasingMixin, View):
    def post(self, request, pk, decision):
        pr = get_object_or_404(PurchaseRequest, pk=pk)
        if decision not in (PurchaseRequest.APPROVED, PurchaseRequest.REJECTED):
            messages.error(request, "Invalid decision.")
            return redirect(reverse("purchasing:request_detail", args=[pk]))

        reason = ""
        if decision == PurchaseRequest.REJECTED:
            reject_form = PurchaseRequestRejectForm(request.POST)
            if reject_form.is_valid():
                reason = reject_form.cleaned_data.get("rejection_reason", "")

        decide_purchase_request(
            pr, approved=(decision == PurchaseRequest.APPROVED), user=request.user, rejection_reason=reason,
        )
        messages.success(request, f"{pr.reference} {decision}.")
        return redirect(reverse("purchasing:request_detail", args=[pk]))


class PurchaseRequestDeleteView(EditPurchasingMixin, DeleteView):
    model = PurchaseRequest
    success_url = reverse_lazy("purchasing:requests")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("purchasing:requests")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Purchase request deleted.")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Purchase Orders
# ---------------------------------------------------------------------------

class PurchaseOrderListView(ViewPurchasingMixin, ListView):
    model = PurchaseOrder
    template_name = "purchasing/order_list.html"
    context_object_name = "orders"
    paginate_by = 30

    def get_queryset(self):
        return PurchaseOrder.objects.select_related("supplier", "related_request")


class PurchaseOrderCreateFromRequestView(EditPurchasingMixin, View):
    def post(self, request, pk):
        pr = get_object_or_404(PurchaseRequest, pk=pk)
        form = PurchaseOrderFromRequestForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please provide a supplier and order date.")
            return redirect(reverse("purchasing:request_detail", args=[pk]))

        try:
            order = create_purchase_order_from_request(
                pr,
                supplier=form.cleaned_data["supplier"],
                order_date=form.cleaned_data["order_date"],
                expected_delivery_date=form.cleaned_data.get("expected_delivery_date"),
                user=request.user,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(reverse("purchasing:request_detail", args=[pk]))

        messages.success(request, f"{order.reference} created from {pr.reference} — set unit prices before sending.")
        return redirect(reverse("purchasing:order_edit", args=[order.pk]))


class PurchaseOrderCreateView(EditPurchasingMixin, View):
    template_name = "purchasing/order_form.html"

    def get(self, request):
        form = PurchaseOrderForm(initial={"order_date": _today()})
        formset = PurchaseOrderLineFormSet()
        return render(request, self.template_name, {"form": form, "formset": formset})

    def post(self, request):
        form = PurchaseOrderForm(request.POST)
        formset = PurchaseOrderLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            order = form.save(commit=False)
            order.created_by = request.user
            order.save()
            formset.instance = order
            formset.save()
            messages.success(request, f"{order.reference} created.")
            return redirect(reverse("purchasing:order_detail", args=[order.pk]))
        return render(request, self.template_name, {"form": form, "formset": formset})


class PurchaseOrderUpdateView(EditPurchasingMixin, View):
    template_name = "purchasing/order_form.html"

    def get(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        form = PurchaseOrderForm(instance=order)
        formset = PurchaseOrderLineFormSet(instance=order)
        return render(request, self.template_name, {"form": form, "formset": formset, "object": order})

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        form = PurchaseOrderForm(request.POST, instance=order)
        formset = PurchaseOrderLineFormSet(request.POST, instance=order)
        if form.is_valid() and formset.is_valid():
            order = form.save()
            formset.instance = order
            formset.save()
            messages.success(request, f"{order.reference} updated.")
            return redirect(reverse("purchasing:order_detail", args=[order.pk]))
        return render(request, self.template_name, {"form": form, "formset": formset, "object": order})


class PurchaseOrderDetailView(ViewPurchasingMixin, View):
    template_name = "purchasing/order_detail.html"

    def get(self, request, pk):
        order = get_object_or_404(
            PurchaseOrder.objects.select_related("supplier", "related_request").prefetch_related("lines__material", "receipts"),
            pk=pk,
        )
        return render(request, self.template_name, {"order": order})


class PurchaseOrderSendView(EditPurchasingMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        if order.status == PurchaseOrder.DRAFT:
            order.status = PurchaseOrder.SENT
            order.save(update_fields=["status"])
            messages.success(request, f"{order.reference} marked as sent to {order.supplier.name}.")
        return redirect(reverse("purchasing:order_detail", args=[pk]))


# ---------------------------------------------------------------------------
# Goods Receipt
# ---------------------------------------------------------------------------

class GoodsReceiptCreateView(EditPurchasingMixin, View):
    template_name = "purchasing/receipt_form.html"

    def get(self, request, pk):
        order = get_object_or_404(PurchaseOrder.objects.prefetch_related("lines__material"), pk=pk)
        outstanding_lines = [line for line in order.lines.all() if line.quantity_outstanding > 0]
        form = GoodsReceiptForm(initial={"receipt_date": _today()})
        return render(request, self.template_name, {"order": order, "form": form, "outstanding_lines": outstanding_lines})

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder.objects.prefetch_related("lines__material"), pk=pk)
        outstanding_lines = [line for line in order.lines.all() if line.quantity_outstanding > 0]
        form = GoodsReceiptForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {"order": order, "form": form, "outstanding_lines": outstanding_lines})

        line_quantities = {}
        for line in outstanding_lines:
            raw = request.POST.get(f"qty_{line.pk}", "").strip()
            if not raw:
                continue
            try:
                qty = float(raw)
            except ValueError:
                continue
            if qty <= 0:
                continue
            line_quantities[line.pk] = min(qty, line.quantity_outstanding)

        if not line_quantities:
            messages.error(request, "Enter a received quantity for at least one item.")
            return render(request, self.template_name, {"order": order, "form": form, "outstanding_lines": outstanding_lines})

        receipt = GoodsReceipt.objects.create(
            purchase_order=order,
            receipt_date=form.cleaned_data["receipt_date"],
            received_by=form.cleaned_data.get("received_by"),
            notes=form.cleaned_data.get("notes", ""),
            created_by=request.user,
        )
        GoodsReceiptLine.objects.bulk_create([
            GoodsReceiptLine(receipt=receipt, order_line_id=line_pk, quantity_received=qty)
            for line_pk, qty in line_quantities.items()
        ])
        receive_goods(receipt, user=request.user)

        messages.success(request, f"{receipt.reference} recorded — stock updated for {order.reference}.")
        return redirect(reverse("purchasing:order_detail", args=[order.pk]))
