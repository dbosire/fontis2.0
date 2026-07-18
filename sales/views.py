from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView, DeleteView

from core.mixins import ModulePermissionRequiredMixin
from crm.services.loyalty import award_points_for_sale
from debts.models import DebtPayment
from debts.services import all_customer_credit_balances, customer_credit_balance, record_debt_payment
from finance.services import sync_journal_for_sale, void_journal_for_sale
from inventory.services import apply_sale_item_stock_deltas, restock_for_deleted_sale
from maintenance.models import JarType

from .forms import SaleForm, SaleItemFormSet
from .models import Sale


class ViewSalesMixin(ModulePermissionRequiredMixin):
    module_name = "sales"
    permission_level = "view"


class EditSalesMixin(ModulePermissionRequiredMixin):
    module_name = "sales"
    permission_level = "edit"


# USE_TZ=False project-wide — naive local time only, matching every other app.
def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


def _parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


class SaleListView(ViewSalesMixin, ListView):
    model = Sale
    template_name = "sales/sale_list.html"
    context_object_name = "sales"
    paginate_by = 30

    def get_template_names(self):
        # Filter-as-you-type: an htmx request only needs the results partial
        # (table + pagination), not the full page with the filter form and sidebar.
        if self.request.htmx:
            return ["sales/sale_results.html"]
        return [self.template_name]

    def get_queryset(self):
        qs = Sale.objects.prefetch_related("items__jar_type")

        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "")
        sale_type = self.request.GET.get("type", "")
        date_start = self.request.GET.get("date_start", "")
        date_end = self.request.GET.get("date_end", "")

        valid_statuses = {str(value) for value, _ in Sale.STATUS_CHOICES}
        valid_types = {str(value) for value, _ in Sale.TYPE_CHOICES}

        if q:
            qs = qs.filter(customer_name__icontains=q)
        if status in valid_statuses:
            qs = qs.filter(status=status)
        if sale_type in valid_types:
            qs = qs.filter(type=sale_type)
        if _parse_date(date_start):
            qs = qs.filter(date_created__date__gte=date_start)
        if _parse_date(date_end):
            qs = qs.filter(date_created__date__lte=date_end)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filters"] = {
            "q": self.request.GET.get("q", ""),
            "status": self.request.GET.get("status", ""),
            "type": self.request.GET.get("type", ""),
            "date_start": self.request.GET.get("date_start", ""),
            "date_end": self.request.GET.get("date_end", ""),
        }
        # preserve the active filters on pagination links without the page param
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        ctx["status_choices"] = Sale.STATUS_CHOICES
        ctx["type_choices"] = Sale.TYPE_CHOICES
        return ctx


class SaleFormView(EditSalesMixin, View):
    template_name = "sales/sale_form.html"

    def get_object(self):
        pk = self.kwargs.get("pk")
        return get_object_or_404(Sale, pk=pk) if pk else None

    def get_extra_context(self, *, is_create):
        jar_type_prices = {str(pk): price for pk, price in JarType.objects.values_list("pk", "pricing")}
        customer_names = list(
            Sale.objects.exclude(customer_name="Guest")
            .values_list("customer_name", flat=True)
            .distinct()
            .order_by("customer_name")
        )
        return {
            "jar_type_prices": jar_type_prices,
            "customer_names": customer_names,
            # Drives both the "this customer has credit" banner and gating the
            # "Paid (Credit)" status option so it can't be picked for a customer with
            # no balance — see sale_form.html's updateCreditUI().
            "credit_balances": all_customer_credit_balances(),
            "is_create": is_create,
        }

    def get(self, request, *args, **kwargs):
        sale = self.get_object()
        initial = {"customer_name": "Guest"} if sale is None else None
        form = SaleForm(instance=sale, initial=initial)
        formset = SaleItemFormSet(instance=sale)
        ctx = {"form": form, "formset": formset, "object": sale, **self.get_extra_context(is_create=sale is None)}
        return render(request, self.template_name, ctx)

    def post(self, request, *args, **kwargs):
        sale = self.get_object()
        is_create = sale is None
        old_items = {}
        if sale is not None:
            old_items = {
                item.pk: (item.jar_type, item.quantity)
                for item in sale.items.select_related("jar_type").all()
            }

        form = SaleForm(request.POST, instance=sale)
        formset = SaleItemFormSet(request.POST, instance=sale)

        if form.is_valid() and formset.is_valid():
            sale = form.save(commit=False)
            # Staff picking "Paid (Credit)" directly on this form is only a status
            # label, not a ledger entry — routing it through record_debt_payment below
            # (same call the auto-apply hook uses) is what actually validates the
            # customer has enough credit and deducts it from CustomerCredit. Hold the
            # real status back until that succeeds, so a bad selection can't silently
            # mark a sale "Credit" with nothing backing it.
            requested_credit = sale.status == Sale.CREDIT
            if requested_credit:
                sale.status = Sale.UNPAID
            sale.save()
            formset.instance = sale
            formset.save()
            sale.recompute_amount()
            sale.save(update_fields=["amount"])

            new_items = {
                item.pk: (item.jar_type, item.quantity)
                for item in sale.items.select_related("jar_type").all()
            }
            apply_sale_item_stock_deltas(old_items, new_items, sale, user=request.user)
            award_points_for_sale(sale, user=request.user)
            sync_journal_for_sale(sale, user=request.user)

            if requested_credit:
                try:
                    record_debt_payment(
                        sale, amount=sale.balance_due, payment_date=_today(),
                        payment_method=DebtPayment.CREDIT,
                        notes="Marked as Credit payment at entry", user=request.user,
                    )
                except ValueError as exc:
                    messages.error(request, f"{exc} Sale saved as Unpaid instead.")
            # A brand-new debt for a customer who already has credit (from an earlier
            # overpayment or prepayment) auto-settles immediately — see
            # debts/services.py::record_debt_payment's CREDIT handling. Scoped to
            # creation only, not edits of an existing sale, so this never re-fires
            # every time someone tweaks item quantities on an already-settled sale.
            # Skipped when Credit was explicitly requested above — that already tried
            # (and, on failure, already explained why), so this wouldn't do anything
            # but silently apply a partial amount after a "no credit" error.
            elif is_create and sale.status == Sale.UNPAID:
                available = customer_credit_balance(sale.customer_name)
                if available > 0:
                    record_debt_payment(
                        sale, amount=min(available, sale.balance_due), payment_date=_today(),
                        payment_method=DebtPayment.CREDIT,
                        notes="Auto-applied from customer credit balance", user=request.user,
                    )

            messages.success(request, "Sale saved.")

            next_url = request.GET.get("next")
            if next_url == "debt":
                return redirect(reverse("debts:individual"))
            return redirect(reverse("sales:list"))

        ctx = {"form": form, "formset": formset, "object": sale, **self.get_extra_context(is_create=is_create)}
        return render(request, self.template_name, ctx)


class SaleBulkUpdateStatusView(EditSalesMixin, View):
    """Bulk-update the payment status of any selected sales, regardless of their current status."""

    def post(self, request, *args, **kwargs):
        sale_ids = request.POST.getlist("sale_ids")
        status = request.POST.get("status")
        valid_statuses = {str(value) for value, _ in Sale.STATUS_CHOICES}

        redirect_url = request.POST.get("next") or ""
        if not url_has_allowed_host_and_scheme(
            redirect_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            redirect_url = reverse("sales:list")

        if not sale_ids:
            messages.error(request, "Select at least one sale first.")
        elif status not in valid_statuses:
            messages.error(request, "Choose a valid payment status.")
        else:
            updated = Sale.objects.filter(pk__in=sale_ids).update(status=status)
            for sale in Sale.objects.filter(pk__in=sale_ids):
                award_points_for_sale(sale, user=request.user)
                sync_journal_for_sale(sale, user=request.user)
            status_label = dict(Sale.STATUS_CHOICES).get(int(status), status)
            messages.success(request, f"Updated {updated} sale{'s' if updated != 1 else ''} to “{status_label}”.")

        return redirect(redirect_url)


class SaleDeleteView(EditSalesMixin, DeleteView):
    model = Sale
    success_url = reverse_lazy("sales:list")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("sales:list")
        return ctx

    def form_valid(self, form):
        restock_for_deleted_sale(self.object, user=self.request.user)
        void_journal_for_sale(self.object, user=self.request.user)
        messages.success(self.request, "Sale deleted.")
        return super().form_valid(form)
