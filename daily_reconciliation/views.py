from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from core.mixins import ModulePermissionRequiredMixin

from .forms import DailyReconciliationForm
from .models import DailyReconciliation
from .services import allocate_cash_deposit, candidate_deposit_transactions, summary_for


class ViewReconciliationMixin(ModulePermissionRequiredMixin):
    module_name = "daily_reconciliation"
    permission_level = "view"


class EditReconciliationMixin(ModulePermissionRequiredMixin):
    module_name = "daily_reconciliation"
    permission_level = "edit"


def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


class TodayReconciliationView(EditReconciliationMixin, View):
    """The daily entry point — enter (or update) today's cash count and see the
    computed expected/actual totals and variances immediately."""

    template_name = "daily_reconciliation/today.html"

    def get(self, request):
        today = _today()
        record = DailyReconciliation.objects.filter(date=today).first()
        form = DailyReconciliationForm(instance=record)
        ctx = {
            "form": form,
            "record": record,
            "today": today,
            "summary": summary_for(today, record.cash_collected if record else None),
            "deposit_candidates": candidate_deposit_transactions(record) if record else [],
        }
        return render(request, self.template_name, ctx)

    def post(self, request):
        today = _today()
        record = DailyReconciliation.objects.filter(date=today).first()
        # The form's `date` field isn't rendered on this page (it's always "today" by
        # definition here) — inject it so the ModelForm still validates cleanly.
        data = request.POST.copy()
        data["date"] = today.isoformat()
        form = DailyReconciliationForm(data, instance=record)
        if form.is_valid():
            record = form.save(commit=False)
            record.date = today
            record.recorded_by = request.user
            record.save()
            messages.success(request, "Today's reconciliation saved.")
            return redirect(reverse("daily_reconciliation:today"))

        ctx = {
            "form": form,
            "record": record,
            "today": today,
            "summary": summary_for(today, record.cash_collected if record else None),
            "deposit_candidates": candidate_deposit_transactions(record) if record else [],
        }
        return render(request, self.template_name, ctx)


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
        return ctx


class CashDepositAllocateView(EditReconciliationMixin, View):
    """Staff confirms one of the candidate M-Pesa transactions services.py surfaced
    as this day's cash deposit. Reachable from either the today page or a past day's
    detail page, so it redirects back to wherever the POST came from."""

    def post(self, request, pk):
        record = get_object_or_404(DailyReconciliation, pk=pk)
        trans_id = request.POST.get("trans_id", "").strip()
        candidate_ids = {t.TransID for t in candidate_deposit_transactions(record)}
        if not trans_id or trans_id not in candidate_ids:
            messages.error(request, "That M-Pesa transaction is no longer a valid match for this day.")
        else:
            allocate_cash_deposit(record, trans_id, user=request.user)
            messages.success(request, "Cash deposit allocated.")
        next_url = request.POST.get("next") or reverse("daily_reconciliation:detail", args=[record.pk])
        return redirect(next_url)
