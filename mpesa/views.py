from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import DetailView, ListView

from core.mixins import ModulePermissionRequiredMixin
from crm.services.sms import send_sms
from sales.models import Sale

from .models import LegacyTransactionAllocation, MpesaC2BTransaction, MpesaTransaction, PaymentLink
from .services.reconciliation import allocate_legacy_transaction, legacy_allocated_total, manual_match


class ViewMpesaMixin(ModulePermissionRequiredMixin):
    module_name = "mpesa"
    permission_level = "view"


class EditMpesaMixin(ModulePermissionRequiredMixin):
    module_name = "mpesa"
    permission_level = "edit"


class MpesaTransactionListView(ViewMpesaMixin, ListView):
    model = MpesaTransaction
    template_name = "mpesa/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 50

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        trans_ids = [txn.TransID for txn in ctx["transactions"] if txn.TransID]
        allocated_by_trans_id = dict(
            LegacyTransactionAllocation.objects.filter(trans_id__in=trans_ids)
            .values("trans_id")
            .annotate(total=Sum("amount"))
            .values_list("trans_id", "total")
        )
        for txn in ctx["transactions"]:
            txn.allocated_amount = allocated_by_trans_id.get(txn.TransID, 0.0)
        return ctx


class TransactionAllocateView(EditMpesaMixin, View):
    """Lets staff apply a legacy MpesaTransaction's amount to one or more customers'
    outstanding debts — for lump-sum payments (e.g. an agent's collected dues
    deposited as one transaction) that don't correspond to any single debt or
    PaymentLink. Reuses the same grouped-by-customer selection UI as Individual Debts."""

    def get(self, request, trans_id):
        txn = get_object_or_404(MpesaTransaction, TransID=trans_id)
        ctx = self._context(txn)
        return render(request, "mpesa/transaction_allocate.html", ctx)

    def post(self, request, trans_id):
        txn = get_object_or_404(MpesaTransaction, TransID=trans_id)
        sale_ids = request.POST.getlist("sale_ids")
        if not sale_ids:
            messages.error(request, "Select at least one debt to allocate this payment to.")
            return redirect(reverse("mpesa:transaction_allocate", args=[trans_id]))
        try:
            sales, total_allocated = allocate_legacy_transaction(trans_id, txn.TransAmount, sale_ids, user=request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(reverse("mpesa:transaction_allocate", args=[trans_id]))
        if not sales:
            messages.warning(request, "Nothing was allocated — the selected debt(s) were already settled.")
            return redirect(reverse("mpesa:transaction_allocate", args=[trans_id]))
        messages.success(
            request,
            f"Allocated KES {total_allocated:,.2f} across {len(sales)} debt{'s' if len(sales) != 1 else ''}.",
        )
        return redirect(reverse("mpesa:list"))

    def _context(self, txn):
        sales = Sale.objects.filter(status__in=[Sale.UNPAID, Sale.PARTIAL]).prefetch_related("items__jar_type", "debt_payments")
        groups = {}
        order = []
        for sale in sales:
            key = sale.customer_name
            if key not in groups:
                groups[key] = {"customer_name": key, "sales": [], "total_amount": 0.0}
                order.append(key)
            groups[key]["sales"].append(sale)
            groups[key]["total_amount"] += sale.balance_due

        allocated = legacy_allocated_total(txn.TransID)
        return {
            "txn": txn,
            "groups": [groups[key] for key in order],
            "allocated": allocated,
            "remaining": float(txn.TransAmount) - allocated,
            "existing_allocations": LegacyTransactionAllocation.objects.filter(trans_id=txn.TransID).select_related("sale"),
        }


class PaymentLinkListView(ViewMpesaMixin, ListView):
    model = PaymentLink
    template_name = "mpesa/payment_link_list.html"
    context_object_name = "links"
    paginate_by = 30

    def get_queryset(self):
        return PaymentLink.objects.prefetch_related("sales")


class PaymentLinkCreateView(EditMpesaMixin, View):
    """Bundles the selected UNPAID sales (must all be one customer) into a single
    PaymentLink and texts it via the existing SMS service — shares the checkbox
    selection UI already built for debts:bulk_update on the Individual Debts page."""

    def post(self, request):
        sale_ids = request.POST.getlist("sale_ids")
        redirect_url = request.POST.get("next") or ""
        if not url_has_allowed_host_and_scheme(
            redirect_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            redirect_url = reverse("debts:individual")

        if not sale_ids:
            messages.error(request, "Select at least one debt first.")
            return redirect(redirect_url)

        sales = Sale.objects.filter(pk__in=sale_ids, status__in=[Sale.UNPAID, Sale.PARTIAL])
        try:
            link = PaymentLink.create_for_sales(sales, user=request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(redirect_url)

        contact_phone = ""
        from contacts.models import Contact
        contact = Contact.objects.filter(name__iexact=link.customer_name).first()
        if contact and contact.phone:
            contact_phone = contact.phone
            link.phone_number = contact_phone
            link.save(update_fields=["phone_number"])

        pay_url = request.build_absolute_uri(reverse("mpesa_public:pay", args=[link.token]))
        if contact_phone:
            message = (
                f"Hi {link.customer_name}, your Fontis Springs balance of KES {link.amount:,.0f} "
                f"can be paid here: {pay_url}"
            )
            send_sms(contact_phone, message, contact=contact, user=request.user)
            messages.success(request, f"Payment link created and sent to {contact_phone}.")
        else:
            messages.warning(
                request,
                f"Payment link created ({pay_url}) but no phone number is on file for "
                f"{link.customer_name} — add one to their contact record and resend.",
            )
        return redirect(redirect_url)


class PaymentLinkDetailView(ViewMpesaMixin, DetailView):
    model = PaymentLink
    template_name = "mpesa/payment_link_detail.html"
    context_object_name = "link"

    def get_queryset(self):
        return PaymentLink.objects.prefetch_related("sales__items__jar_type")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pay_url"] = self.request.build_absolute_uri(reverse("mpesa_public:pay", args=[self.object.token]))
        return ctx


class PaymentLinkResendView(EditMpesaMixin, View):
    def post(self, request, pk):
        link = get_object_or_404(PaymentLink, pk=pk)
        if link.status != PaymentLink.PENDING:
            messages.error(request, "Only pending payment links can be resent.")
            return redirect(reverse("mpesa:payment_links"))
        if not link.phone_number:
            messages.error(request, "This link has no phone number on file.")
            return redirect(reverse("mpesa:payment_links"))

        pay_url = request.build_absolute_uri(reverse("mpesa_public:pay", args=[link.token]))
        message = f"Hi {link.customer_name}, your Fontis Springs balance of KES {link.amount:,.0f} can be paid here: {pay_url}"
        send_sms(link.phone_number, message, user=request.user)
        messages.success(request, f"Payment link resent to {link.phone_number}.")
        return redirect(reverse("mpesa:payment_links"))


class PaymentLinkCancelView(EditMpesaMixin, View):
    def post(self, request, pk):
        link = get_object_or_404(PaymentLink, pk=pk)
        if link.status == PaymentLink.PENDING:
            link.status = PaymentLink.CANCELLED
            link.save(update_fields=["status"])
            messages.success(request, "Payment link cancelled.")
        return redirect(reverse("mpesa:payment_links"))


class ReconciliationListView(ViewMpesaMixin, ListView):
    model = MpesaC2BTransaction
    template_name = "mpesa/reconciliation_list.html"
    context_object_name = "transactions"
    paginate_by = 30

    def get_queryset(self):
        return MpesaC2BTransaction.objects.exclude(status=MpesaC2BTransaction.MATCHED).select_related("matched_payment_link")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pending_links"] = PaymentLink.objects.filter(status=PaymentLink.PENDING).order_by("-date_created")
        return ctx


class ReconciliationMatchView(EditMpesaMixin, View):
    def post(self, request, pk):
        c2b_transaction = get_object_or_404(MpesaC2BTransaction, pk=pk)
        link_id = request.POST.get("payment_link_id")
        link = get_object_or_404(PaymentLink, pk=link_id)
        manual_match(c2b_transaction, link, user=request.user)
        messages.success(request, f"Matched {c2b_transaction.trans_id} to {link.customer_name}'s payment link.")
        return redirect(reverse("mpesa:reconciliation"))
