from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from core.mixins import ModulePermissionRequiredMixin

from .forms import DailyReconciliationForm
from .models import DailyReconciliation
from .services import (
    allocate_cash_deposit,
    candidate_deposit_transactions,
    deposit_variance,
    search_deposit_transactions,
    summary_for,
    valid_deposit_transaction,
)


class ViewReconciliationMixin(ModulePermissionRequiredMixin):
    module_name = "daily_reconciliation"
    permission_level = "view"


class EditReconciliationMixin(ModulePermissionRequiredMixin):
    module_name = "daily_reconciliation"
    permission_level = "edit"


def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


class ReconciliationEntryView(EditReconciliationMixin, View):
    """The cash-entry point — defaults to today via /reconciliation/, but any date
    can be entered or corrected via ?date=YYYY-MM-DD, e.g. to backfill a day staff
    forgot to record. Future dates are rejected outright: there's no cash to count
    for a day that hasn't happened yet."""

    template_name = "daily_reconciliation/today.html"

    def _target_date(self, request):
        raw = request.GET.get("date") or request.POST.get("date")
        if raw:
            try:
                return date.fromisoformat(raw)
            except ValueError:
                pass
        return _today()

    def _render(self, request, target, form=None):
        record = DailyReconciliation.objects.filter(date=target).first()
        ctx = {
            "form": form or DailyReconciliationForm(instance=record),
            "record": record,
            "target_date": target,
            "is_today": target == _today(),
            "max_date": _today(),
            "summary": summary_for(target, record.cash_collected if record else None),
            "deposit_candidates": candidate_deposit_transactions(record) if record else [],
            "deposit_variance": deposit_variance(record) if record else None,
        }
        return render(request, self.template_name, ctx)

    def get(self, request):
        return self._render(request, self._target_date(request))

    def post(self, request):
        target = self._target_date(request)
        if target > _today():
            messages.error(request, "Can't record cash for a future date.")
            return redirect(f"{reverse('daily_reconciliation:today')}?date={target.isoformat()}")

        record = DailyReconciliation.objects.filter(date=target).first()
        # The form's `date` field isn't rendered on this page — inject the resolved
        # target date so the ModelForm still validates cleanly.
        data = request.POST.copy()
        data["date"] = target.isoformat()
        form = DailyReconciliationForm(data, instance=record)
        if form.is_valid():
            record = form.save(commit=False)
            record.date = target
            record.recorded_by = request.user
            record.save()
            messages.success(request, f"Reconciliation for {target:%d %b %Y} saved.")
            return redirect(f"{reverse('daily_reconciliation:today')}?date={target.isoformat()}")

        return self._render(request, target, form=form)


class DailyReconciliationListView(ViewReconciliationMixin, ListView):
    model = DailyReconciliation
    template_name = "daily_reconciliation/list.html"
    context_object_name = "records"
    paginate_by = 30

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for record in ctx["records"]:
            record.summary = summary_for(record.date, record.cash_collected)
        return ctx


class DailyReconciliationDetailView(ViewReconciliationMixin, DetailView):
    model = DailyReconciliation
    template_name = "daily_reconciliation/detail.html"
    context_object_name = "record"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["summary"] = summary_for(self.object.date, self.object.cash_collected)
        ctx["deposit_candidates"] = candidate_deposit_transactions(self.object)
        ctx["deposit_variance"] = deposit_variance(self.object)
        return ctx


class CashDepositAllocateView(EditReconciliationMixin, View):
    """Staff confirms an M-Pesa transaction — from either the auto-matched
    candidates or a search result — as this day's cash deposit. Reachable from
    either the today page or a past day's detail page, so it redirects back to
    wherever the POST came from."""

    def post(self, request, pk):
        record = get_object_or_404(DailyReconciliation, pk=pk)
        trans_id = request.POST.get("trans_id", "").strip()
        depositor_name = request.POST.get("depositor_name", "").strip()
        if not trans_id or not valid_deposit_transaction(record, trans_id):
            messages.error(request, "That M-Pesa transaction is no longer a valid match for this day.")
        elif not depositor_name:
            messages.error(request, "Enter who deposited the cash before allocating.")
        else:
            allocate_cash_deposit(record, trans_id, depositor_name, user=request.user)
            messages.success(request, "Cash deposit allocated.")
        next_url = request.POST.get("next") or reverse("daily_reconciliation:detail", args=[record.pk])
        return redirect(next_url)


class CashDepositSearchView(EditReconciliationMixin, View):
    """htmx-backed search fallback for the Cash Deposit card — lets staff find any
    M-Pesa transaction by TransID, name, phone, or amount, for cases the
    auto-matched (exact-amount) candidates miss."""

    def get(self, request, pk):
        record = get_object_or_404(DailyReconciliation, pk=pk)
        results = search_deposit_transactions(record, request.GET.get("q", ""))
        # This view's own path is the search endpoint, not the reconciliation page —
        # the caller passes back where to redirect to after an allocation via ?next=.
        next_url = request.GET.get("next") or reverse("daily_reconciliation:detail", args=[record.pk])
        return render(
            request, "daily_reconciliation/_deposit_search_results.html",
            {"results": results, "record": record, "next_url": next_url},
        )
