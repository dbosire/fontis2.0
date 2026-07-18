import base64
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Max, Sum
from django.db.models.functions import Lower
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from core.exports import build_xlsx, render_pdf
from core.mixins import ModulePermissionRequiredMixin
from mpesa.models import PaymentLink
from mpesa.services.daraja import MPESA_TILL_NUMBER
from sales.models import Sale
from system_info.services import get_settings_dict

from .forms import DebtPaymentForm, PrepaymentForm
from .models import CustomerCredit, DebtPayment
from .services import record_debt_payment, record_prepayment

OUTSTANDING_STATUSES = [Sale.UNPAID, Sale.PARTIAL]


def _credit_balances_for(customer_names):
    """Batched credit-balance lookup for a page's worth of customers at once, so the
    Grouped/Individual Debts list pages don't run one query per row. Matches
    case-insensitively (grouped on a lowercased name) to stay consistent with
    debts/services.py::customer_credit_balance's iexact semantics — a Sale's
    customer_name and a CustomerCredit's customer_name aren't guaranteed to match case
    exactly, being two independently-typed free-text fields."""
    if not customer_names:
        return {}
    lowered = [name.lower() for name in customer_names]
    rows = (
        CustomerCredit.objects.annotate(lower_name=Lower("customer_name"))
        .filter(lower_name__in=lowered)
        .values("lower_name")
        .annotate(balance=Sum("amount"))
    )
    balance_by_lower = {row["lower_name"]: row["balance"] for row in rows if row["balance"] and row["balance"] > 0.01}
    return {name: balance_by_lower[name.lower()] for name in customer_names if name.lower() in balance_by_lower}


# USE_TZ=False project-wide — naive local time only, matching every other app.
def _now():
    return datetime.now(ZoneInfo("Africa/Nairobi")).replace(tzinfo=None)


class ViewDebtsMixin(ModulePermissionRequiredMixin):
    module_name = "debts"
    permission_level = "view"


class EditDebtsMixin(ModulePermissionRequiredMixin):
    module_name = "debts"
    permission_level = "edit"


def _grouped_debts_queryset(q=""):
    # Grouped in Python, not a DB .annotate(Sum("amount")) — balance_due depends on
    # each Sale's related debt_payments, which isn't a plain column to sum in the DB.
    sales = Sale.objects.filter(status__in=OUTSTANDING_STATUSES).prefetch_related("debt_payments")
    if q:
        sales = sales.filter(customer_name__icontains=q)
    groups = {}
    order = []
    for sale in sales:
        key = sale.customer_name
        if key not in groups:
            groups[key] = {"customer_name": key, "total_amount": 0.0, "total_orders": 0}
            order.append(key)
        groups[key]["total_amount"] += sale.balance_due
        groups[key]["total_orders"] += 1
    return sorted((groups[key] for key in order), key=lambda g: -g["total_amount"])


class DebtGroupedListView(ViewDebtsMixin, ListView):
    template_name = "debts/debt_grouped_list.html"
    context_object_name = "grouped_debts"

    def get_template_names(self):
        # Filter-as-you-type: an htmx request only needs the results partial (table +
        # footer), not the full page with the search form and sidebar — mirrors
        # sales/views.py::SaleListView.
        if self.request.htmx:
            return ["debts/debt_grouped_results.html"]
        return [self.template_name]

    def get_queryset(self):
        return _grouped_debts_queryset(self.request.GET.get("q", "").strip())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["grand_total"] = sum(row["total_amount"] for row in ctx["grouped_debts"])
        ctx["q"] = self.request.GET.get("q", "")
        credit_balances = _credit_balances_for([row["customer_name"] for row in ctx["grouped_debts"]])
        for row in ctx["grouped_debts"]:
            row["credit_balance"] = credit_balances.get(row["customer_name"])
        return ctx


class DebtIndividualListView(ViewDebtsMixin, ListView):
    """Individual unpaid Sale rows grouped by customer — so a customer with several
    dated debts shows as one group (one checkbox to select them all, one total), with
    a link to the most recent payment link sent to them, if any."""

    template_name = "debts/debt_individual_list.html"
    context_object_name = "groups"
    paginate_by = 20

    def get_template_names(self):
        if self.request.htmx:
            return ["debts/debt_individual_results.html"]
        return [self.template_name]

    def get_queryset(self):
        sales = Sale.objects.filter(status__in=OUTSTANDING_STATUSES).prefetch_related("items__jar_type", "debt_payments")
        q = self.request.GET.get("q", "").strip()
        if q:
            sales = sales.filter(customer_name__icontains=q)
        groups = {}
        order = []
        for sale in sales:
            key = sale.customer_name
            if key not in groups:
                groups[key] = {"customer_name": key, "sales": [], "total_amount": 0.0}
                order.append(key)
            groups[key]["sales"].append(sale)
            groups[key]["total_amount"] += sale.balance_due
        return [groups[key] for key in order]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        groups = ctx["groups"]
        customer_names = [g["customer_name"] for g in groups]
        latest_link_by_customer = {}
        for link in PaymentLink.objects.filter(customer_name__in=customer_names):
            # PaymentLink's default ordering is -date_created, so the first row seen
            # per customer here is their most recent link.
            latest_link_by_customer.setdefault(link.customer_name, link)
        for group in groups:
            group["latest_link"] = latest_link_by_customer.get(group["customer_name"])
        credit_balances = _credit_balances_for(customer_names)
        for group in groups:
            group["credit_balance"] = credit_balances.get(group["customer_name"])
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


class DebtExcelExportView(ViewDebtsMixin, ListView):
    def get(self, request, *args, **kwargs):
        rows = [[row["customer_name"], row["total_amount"], row["total_orders"]] for row in _grouped_debts_queryset()]
        return build_xlsx(["Customer Name", "Total Sales", "Total Orders"], rows, filename="debts_report.xlsx")


class DebtPdfExportView(ViewDebtsMixin, ListView):
    def get(self, request, *args, **kwargs):
        grouped = list(_grouped_debts_queryset())
        grand_total = sum(row["total_amount"] for row in grouped)
        return render_pdf(
            "debts/pdf_report.html",
            {"grouped_debts": grouped, "grand_total": grand_total},
            filename="debts_report.pdf",
        )


def _logo_data_uri():
    """Base64-embed the site logo for the PDF renderer. xhtml2pdf resolves relative
    <img src> paths through a link_callback this app doesn't configure, so a plain
    MEDIA_URL src silently fails to render — a data: URI sidesteps that entirely.
    Cached since this reads and re-encodes a file from disk on every miss."""
    logo_rel = get_settings_dict().get("logo") or ""
    if not logo_rel:
        return ""
    cache_key = f"debts_invoice_logo_data_uri:{logo_rel}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    path = os.path.join(str(settings.MEDIA_ROOT), logo_rel)
    if not os.path.exists(path):
        cache.set(cache_key, "", timeout=3600)
        return ""
    ext = os.path.splitext(path)[1].lstrip(".").lower() or "png"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    data_uri = f"data:image/{ext};base64,{encoded}"
    cache.set(cache_key, data_uri, timeout=3600)
    return data_uri


def _invoice_context(request, customer):
    """Shared by the in-app HTML preview and the downloadable PDF, so the two never
    drift apart on what an invoice actually contains."""
    sales = Sale.objects.filter(customer_name=customer, status__in=OUTSTANDING_STATUSES).prefetch_related("items__jar_type", "debt_payments")
    sale_ids = [sale.pk for sale in sales]
    total = sum(sale.balance_due for sale in sales)

    # Same "pay this online" link a customer would already have from an SMS, if staff
    # sent one and it's still usable — surfaced here too since a printed/emailed
    # invoice is often the first thing a customer actually reads.
    payment_link = PaymentLink.objects.filter(customer_name=customer, status=PaymentLink.PENDING).first()
    if payment_link and payment_link.is_expired:
        payment_link = None
    pay_url = request.build_absolute_uri(reverse("mpesa_public:pay", args=[payment_link.token])) if payment_link else ""

    return {
        "customer": customer,
        "sales": sales,
        "total": total,
        "mpesa_till_number": MPESA_TILL_NUMBER,
        "payment_link": payment_link,
        "pay_url": pay_url,
        "invoice_number": f"FS-INV-{min(sale_ids):06d}" if sale_ids else "FS-INV-000000",
        "issue_date": _now(),
    }


class InvoicePreviewView(ViewDebtsMixin, View):
    """In-app, styled preview of a customer's invoice, with a button to download the
    PDF version — reached from the "Invoice" link on Grouped Debts."""

    def get(self, request, *args, **kwargs):
        customer = request.GET.get("customer", "")
        ctx = _invoice_context(request, customer)
        ctx["fontis_site"] = get_settings_dict()
        return render(request, "debts/invoice_preview.html", ctx)


class InvoicePdfView(ViewDebtsMixin, View):
    def get(self, request, *args, **kwargs):
        customer = request.GET.get("customer", "")
        ctx = _invoice_context(request, customer)
        ctx["fontis_site_name"] = get_settings_dict().get("short_name", "Fontis Springs")
        ctx["logo_data_uri"] = _logo_data_uri()
        return render_pdf("debts/invoice.html", ctx, filename=f"invoice_{customer}.pdf")


class DebtBulkUpdateStatusView(EditDebtsMixin, View):
    """Bulk-clear or reassign the payment status of selected individual debts."""

    def post(self, request, *args, **kwargs):
        sale_ids = request.POST.getlist("sale_ids")
        status = request.POST.get("status")
        valid_statuses = {str(value) for value, _ in Sale.STATUS_CHOICES}

        redirect_url = request.POST.get("next") or ""
        if not url_has_allowed_host_and_scheme(redirect_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            redirect_url = reverse("debts:individual")

        if not sale_ids:
            messages.error(request, "Select at least one debt first.")
        elif status not in valid_statuses:
            messages.error(request, "Choose a valid payment status.")
        else:
            status = int(status)
            # Only touch rows that are still outstanding at the time of the update, so
            # a stale checked box from an already-cleared debt can't double-apply.
            matched = list(Sale.objects.filter(pk__in=sale_ids, status__in=OUTSTANDING_STATUSES))
            updated = 0
            if status in (Sale.CASH, Sale.MPESA):
                # Route through record_debt_payment for each debt's *remaining*
                # balance (not its original amount) rather than a bare status flip —
                # keeps the DebtPayment ledger accurate for a debt that was already
                # partially paid.
                method = DebtPayment.CASH if status == Sale.CASH else DebtPayment.MPESA
                for sale in matched:
                    try:
                        record_debt_payment(
                            sale, amount=sale.balance_due, payment_date=_now().date(),
                            payment_method=method, notes="Bulk-marked from Individual Debts",
                            user=request.user,
                        )
                        updated += 1
                    except ValueError:
                        continue
            else:
                # Unresolved — no payment implied, same direct flip as before.
                matched_ids = [sale.pk for sale in matched]
                updated = Sale.objects.filter(pk__in=matched_ids).update(status=status)

            status_label = dict(Sale.STATUS_CHOICES).get(status, status)
            if updated:
                messages.success(request, f"Updated {updated} debt{'s' if updated != 1 else ''} to “{status_label}”.")
            else:
                messages.warning(request, "None of the selected debts could be updated (they may already be cleared).")

        return redirect(redirect_url)


class DebtDetailView(ViewDebtsMixin, View):
    """Per-debt detail — line items, payment history, and (if a balance remains) a
    form to record a new payment against this specific Sale. Mirrors
    finance/views.py::BillDetailView."""

    template_name = "debts/debt_detail.html"

    def get(self, request, pk):
        sale = get_object_or_404(Sale.objects.prefetch_related("items__jar_type", "debt_payments"), pk=pk)
        return render(request, self.template_name, {
            "sale": sale,
            "form": DebtPaymentForm(initial={"payment_date": _now().date()}),
        })


class DebtPaymentCreateView(EditDebtsMixin, View):
    def post(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        form = DebtPaymentForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                record_debt_payment(
                    sale, amount=data["amount"], payment_date=data["payment_date"],
                    payment_method=data["payment_method"], notes=data["notes"], user=request.user,
                )
                messages.success(request, f"Payment of KES {data['amount']:,.2f} recorded for {sale.customer_name}.")
            except ValueError as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, "Could not record that payment.")
        return redirect(reverse("debts:sale_detail", args=[pk]))


class PrepaymentCreateView(EditDebtsMixin, View):
    """Records cash received from a customer with no debt to apply it to yet. Reuses
    the same customer_names autocomplete already built for the Sale form
    (sales/views.py::SaleFormView.get_extra_context)."""

    template_name = "debts/prepayment_form.html"

    def _customer_names(self):
        return list(
            Sale.objects.exclude(customer_name="Guest")
            .values_list("customer_name", flat=True)
            .distinct()
            .order_by("customer_name")
        )

    def get(self, request):
        form = PrepaymentForm(initial={"payment_date": _now().date()})
        return render(request, self.template_name, {"form": form, "customer_names": self._customer_names()})

    def post(self, request):
        form = PrepaymentForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                record_prepayment(
                    data["customer_name"], amount=data["amount"], payment_date=data["payment_date"],
                    payment_method=data["payment_method"], notes=data["notes"], user=request.user,
                )
                messages.success(
                    request,
                    f"Prepayment of KES {data['amount']:,.2f} recorded for {data['customer_name']}.",
                )
                return redirect(reverse("debts:individual"))
            except ValueError as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, "Could not record that prepayment.")
        return render(request, self.template_name, {"form": form, "customer_names": self._customer_names()})


class CustomerCreditListView(ViewDebtsMixin, ListView):
    """Every customer with a nonzero credit balance — the "track it as they utilize
    it" view, linking through to each customer's full ledger history."""

    template_name = "debts/customer_credit_list.html"
    context_object_name = "balances"

    def get_queryset(self):
        rows = (
            CustomerCredit.objects.annotate(lower_name=Lower("customer_name"))
            .values("lower_name")
            .annotate(balance=Sum("amount"), display_name=Max("customer_name"))
            .order_by("-balance")
        )
        return [row for row in rows if row["balance"] and row["balance"] > 0.01]


class CustomerCreditDetailView(ViewDebtsMixin, View):
    """customer_name comes from a query param (?customer=), not a URL path segment —
    mirrors debts:invoice_preview, since a free-text customer name could contain
    characters (like /) that don't route cleanly as part of a path."""

    template_name = "debts/customer_credit_detail.html"

    def get(self, request):
        customer_name = request.GET.get("customer", "")
        entries = CustomerCredit.objects.filter(customer_name__iexact=customer_name).select_related("related_sale")
        if not entries.exists():
            raise Http404("No credit history for this customer.")
        balance = entries.aggregate(total=Sum("amount"))["total"] or 0
        return render(request, self.template_name, {
            "customer_name": customer_name,
            "entries": entries,
            "balance": round(balance, 2),
        })
