import base64
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from core.exports import build_xlsx, render_pdf
from core.mixins import ModulePermissionRequiredMixin
from crm.services.loyalty import award_points_for_sale
from finance.services import sync_journal_for_sale
from mpesa.models import PaymentLink
from mpesa.services.daraja import MPESA_SHORTCODE
from sales.models import Sale
from system_info.services import get_settings_dict


# USE_TZ=False project-wide — naive local time only, matching every other app.
def _now():
    return datetime.now(ZoneInfo("Africa/Nairobi")).replace(tzinfo=None)


class ViewDebtsMixin(ModulePermissionRequiredMixin):
    module_name = "debts"
    permission_level = "view"


class EditDebtsMixin(ModulePermissionRequiredMixin):
    module_name = "debts"
    permission_level = "edit"


def _grouped_debts_queryset():
    return (
        Sale.objects.filter(status=Sale.UNPAID)
        .values("customer_name")
        .annotate(total_amount=Sum("amount"), total_orders=Count("id"))
        .order_by("-total_amount")
    )


class DebtGroupedListView(ViewDebtsMixin, ListView):
    template_name = "debts/debt_grouped_list.html"
    context_object_name = "grouped_debts"

    def get_queryset(self):
        return _grouped_debts_queryset()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["grand_total"] = sum(row["total_amount"] for row in ctx["grouped_debts"])
        return ctx


class DebtIndividualListView(ViewDebtsMixin, ListView):
    """Individual unpaid Sale rows grouped by customer — so a customer with several
    dated debts shows as one group (one checkbox to select them all, one total), with
    a link to the most recent payment link sent to them, if any."""

    template_name = "debts/debt_individual_list.html"
    context_object_name = "groups"
    paginate_by = 20

    def get_queryset(self):
        sales = Sale.objects.filter(status=Sale.UNPAID).prefetch_related("items__jar_type")
        groups = {}
        order = []
        for sale in sales:
            key = sale.customer_name
            if key not in groups:
                groups[key] = {"customer_name": key, "sales": [], "total_amount": 0.0}
                order.append(key)
            groups[key]["sales"].append(sale)
            groups[key]["total_amount"] += sale.amount
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
    sales = Sale.objects.filter(customer_name=customer, status=Sale.UNPAID).prefetch_related("items__jar_type")
    sale_ids = [sale.pk for sale in sales]
    total = sum(sale.amount for sale in sales)

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
        "mpesa_till_number": MPESA_SHORTCODE,
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
            # Only touch rows that are still unpaid at the time of the update, so a
            # stale checked box from an already-cleared debt can't double-apply.
            matched_ids = list(Sale.objects.filter(pk__in=sale_ids, status=Sale.UNPAID).values_list("pk", flat=True))
            updated = Sale.objects.filter(pk__in=matched_ids).update(status=status)
            for sale in Sale.objects.filter(pk__in=matched_ids):
                award_points_for_sale(sale, user=request.user)
                sync_journal_for_sale(sale, user=request.user)
            status_label = dict(Sale.STATUS_CHOICES).get(int(status), status)
            if updated:
                messages.success(request, f"Updated {updated} debt{'s' if updated != 1 else ''} to “{status_label}”.")
            else:
                messages.warning(request, "None of the selected debts could be updated (they may already be cleared).")

        return redirect(redirect_url)
