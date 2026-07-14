from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from core.exports import build_xlsx
from core.mixins import ModulePermissionRequiredMixin

from .forms import (
    AccountForm, AccountMappingForm, BankAccountForm, BankStatementLineForm,
    BillForm, BillPaymentForm, BudgetForm, BudgetLineFormSet, ExpenseCategoryAccountMappingForm,
    FixedAssetForm, JournalEntryForm, JournalLineFormSet, PettyCashFundForm,
    PettyCashReplenishForm, PettyCashVoucherForm, RunDepreciationForm, TaxRateForm,
)
from .models import (
    Account, AccountMapping, BankAccount, BankStatementLine, Bill, BillPayment,
    Budget, BudgetLine, DepreciationEntry, ExpenseCategoryAccountMapping, FixedAsset,
    JournalEntry, JournalLine, PettyCashFund, PettyCashVoucher, TaxRate,
)
from .services import (
    post_journal_for_bill_payment, post_journal_for_petty_cash_replenishment,
    post_journal_for_petty_cash_voucher, run_depreciation, sync_journal_for_bill,
    void_journal_entry, void_journal_for_bill,
)


class ViewFinanceMixin(ModulePermissionRequiredMixin):
    module_name = "finance"
    permission_level = "view"


class EditFinanceMixin(ModulePermissionRequiredMixin):
    module_name = "finance"
    permission_level = "edit"


# See reports/views.py for why this can't just be timezone.localdate() (USE_TZ=False).
def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


# ---------------------------------------------------------------------------
# Phase A: Chart of Accounts + General Ledger
# ---------------------------------------------------------------------------

class AccountListView(ViewFinanceMixin, ListView):
    model = Account
    template_name = "finance/account_list.html"
    context_object_name = "accounts"

    def get_queryset(self):
        return Account.objects.select_related("parent")


class AccountCreateView(EditFinanceMixin, CreateView):
    model = Account
    form_class = AccountForm
    template_name = "finance/account_form.html"
    success_url = reverse_lazy("finance:accounts")

    def form_valid(self, form):
        messages.success(self.request, "Account added.")
        return super().form_valid(form)


class AccountUpdateView(EditFinanceMixin, UpdateView):
    model = Account
    form_class = AccountForm
    template_name = "finance/account_form.html"
    success_url = reverse_lazy("finance:accounts")

    def form_valid(self, form):
        messages.success(self.request, "Account updated.")
        return super().form_valid(form)


class AccountDeleteView(EditFinanceMixin, DeleteView):
    model = Account
    success_url = reverse_lazy("finance:accounts")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("finance:accounts")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Account deleted.")
        return super().form_valid(form)


class JournalEntryListView(ViewFinanceMixin, ListView):
    model = JournalEntry
    template_name = "finance/journal_entry_list.html"
    context_object_name = "entries"
    paginate_by = 50

    def get_queryset(self):
        qs = JournalEntry.objects.prefetch_related("lines__account")
        source = self.request.GET.get("source", "")
        if source:
            qs = qs.filter(source=source)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["source_choices"] = JournalEntry.SOURCE_CHOICES
        ctx["selected_source"] = self.request.GET.get("source", "")
        return ctx


class JournalEntryCreateView(EditFinanceMixin, View):
    template_name = "finance/journal_entry_form.html"

    def get(self, request):
        form = JournalEntryForm(initial={"date": _today()})
        formset = JournalLineFormSet()
        return render(request, self.template_name, {"form": form, "formset": formset})

    def post(self, request):
        form = JournalEntryForm(request.POST)
        formset = JournalLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            lines = []
            for line_form in formset:
                if not line_form.cleaned_data or line_form.cleaned_data.get("DELETE"):
                    continue
                lines.append((
                    line_form.cleaned_data["account"],
                    line_form.cleaned_data.get("debit") or 0,
                    line_form.cleaned_data.get("credit") or 0,
                ))
            from .services import UnbalancedEntryError, post_journal_entry
            try:
                post_journal_entry(
                    form.cleaned_data["date"], form.cleaned_data["description"], lines,
                    source=JournalEntry.MANUAL, user=request.user,
                )
                messages.success(request, "Journal entry posted.")
                return redirect(reverse("finance:journal_entries"))
            except UnbalancedEntryError as exc:
                messages.error(request, str(exc))
        return render(request, self.template_name, {"form": form, "formset": formset})


class JournalEntryVoidView(EditFinanceMixin, View):
    def post(self, request, pk):
        entry = get_object_or_404(JournalEntry, pk=pk)
        void_journal_entry(entry, user=request.user)
        messages.success(request, f"{entry.reference} voided.")
        return redirect(reverse("finance:journal_entries"))


class TrialBalanceView(ViewFinanceMixin, View):
    template_name = "finance/trial_balance.html"

    def get(self, request):
        as_of = request.GET.get("as_of") or _today().isoformat()
        rows = []
        total_debit = total_credit = 0
        for account in Account.objects.filter(is_active=True):
            balance = account.balance_as_of(as_of)
            if not balance:
                continue
            debit = balance if account.normal_balance == "debit" else 0
            credit = balance if account.normal_balance == "credit" else 0
            total_debit += debit
            total_credit += credit
            rows.append({"account": account, "debit": debit, "credit": credit})
        ctx = {
            "rows": rows, "as_of": as_of,
            "total_debit": round(total_debit, 2), "total_credit": round(total_credit, 2),
        }
        return render(request, self.template_name, ctx)


# ---------------------------------------------------------------------------
# Phase B: account mapping settings
# ---------------------------------------------------------------------------

class AccountMappingUpdateView(EditFinanceMixin, View):
    template_name = "finance/account_mapping_form.html"

    def get(self, request):
        mapping = AccountMapping.get_solo()
        form = AccountMappingForm(instance=mapping)
        category_mappings = ExpenseCategoryAccountMapping.objects.select_related("account")
        return render(request, self.template_name, {
            "form": form, "category_mappings": category_mappings,
            "category_form": ExpenseCategoryAccountMappingForm(),
        })

    def post(self, request):
        mapping = AccountMapping.get_solo()
        form = AccountMappingForm(request.POST, instance=mapping)
        if form.is_valid():
            form.save()
            messages.success(request, "Finance account mapping updated.")
            return redirect(reverse("finance:mapping"))
        category_mappings = ExpenseCategoryAccountMapping.objects.select_related("account")
        return render(request, self.template_name, {
            "form": form, "category_mappings": category_mappings,
            "category_form": ExpenseCategoryAccountMappingForm(),
        })


class ExpenseCategoryMappingCreateView(EditFinanceMixin, View):
    def post(self, request):
        form = ExpenseCategoryAccountMappingForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category mapping saved.")
        else:
            messages.error(request, "Could not save that category mapping — it may already exist.")
        return redirect(reverse("finance:mapping"))


class ExpenseCategoryMappingDeleteView(EditFinanceMixin, View):
    def post(self, request, pk):
        ExpenseCategoryAccountMapping.objects.filter(pk=pk).delete()
        messages.success(request, "Category mapping removed.")
        return redirect(reverse("finance:mapping"))


# ---------------------------------------------------------------------------
# Phase C: Cashbook, Bank Reconciliation, Petty Cash
# ---------------------------------------------------------------------------

class CashbookView(ViewFinanceMixin, View):
    template_name = "finance/cashbook.html"

    def get(self, request):
        account_id = request.GET.get("account", "")
        cash_accounts = Account.objects.filter(is_cash_account=True)
        lines_qs = JournalLine.objects.filter(
            account__is_cash_account=True, entry__status=JournalEntry.POSTED
        ).select_related("account", "entry").order_by("entry__date", "entry__id")
        if account_id:
            lines_qs = lines_qs.filter(account_id=account_id)

        rows = []
        balance = 0
        for line in lines_qs:
            net = line.debit - line.credit
            balance += net
            rows.append({"line": line, "net": net, "balance": round(balance, 2)})

        ctx = {"rows": rows, "cash_accounts": cash_accounts, "selected_account": account_id}
        return render(request, self.template_name, ctx)


class BankAccountListView(ViewFinanceMixin, ListView):
    model = BankAccount
    template_name = "finance/bank_account_list.html"
    context_object_name = "bank_accounts"


class BankAccountCreateView(EditFinanceMixin, CreateView):
    model = BankAccount
    form_class = BankAccountForm
    template_name = "finance/bank_account_form.html"
    success_url = reverse_lazy("finance:bank_accounts")

    def form_valid(self, form):
        messages.success(self.request, "Bank account added.")
        return super().form_valid(form)


class BankStatementLineListView(ViewFinanceMixin, View):
    template_name = "finance/bank_statement_lines.html"

    def get(self, request, pk):
        bank_account = get_object_or_404(BankAccount, pk=pk)
        lines = bank_account.statement_lines.all()
        form = BankStatementLineForm()
        return render(request, self.template_name, {"bank_account": bank_account, "lines": lines, "form": form})

    def post(self, request, pk):
        bank_account = get_object_or_404(BankAccount, pk=pk)
        form = BankStatementLineForm(request.POST)
        if form.is_valid():
            line = form.save(commit=False)
            line.bank_account = bank_account
            line.save()
            messages.success(request, "Statement line added.")
            return redirect(reverse("finance:bank_statement_lines", args=[bank_account.pk]))
        lines = bank_account.statement_lines.all()
        return render(request, self.template_name, {"bank_account": bank_account, "lines": lines, "form": form})


class BankReconciliationView(EditFinanceMixin, View):
    template_name = "finance/bank_reconciliation.html"

    def get(self, request, pk):
        bank_account = get_object_or_404(BankAccount, pk=pk)
        unmatched_statement = bank_account.statement_lines.filter(reconciled=False)
        matched_line_ids = BankStatementLine.objects.filter(
            matched_journal_line__isnull=False
        ).values_list("matched_journal_line_id", flat=True)
        unmatched_journal = (
            JournalLine.objects.filter(account=bank_account.gl_account, entry__status=JournalEntry.POSTED)
            .exclude(pk__in=matched_line_ids)
            .select_related("entry")
        )
        ctx = {"bank_account": bank_account, "unmatched_statement": unmatched_statement, "unmatched_journal": unmatched_journal}
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        bank_account = get_object_or_404(BankAccount, pk=pk)
        statement_line_id = request.POST.get("statement_line_id")
        journal_line_id = request.POST.get("journal_line_id")
        statement_line = get_object_or_404(BankStatementLine, pk=statement_line_id, bank_account=bank_account)
        journal_line = get_object_or_404(JournalLine, pk=journal_line_id)
        statement_line.reconciled = True
        statement_line.matched_journal_line = journal_line
        statement_line.save(update_fields=["reconciled", "matched_journal_line"])
        messages.success(request, "Matched.")
        return redirect(reverse("finance:bank_reconciliation", args=[bank_account.pk]))


class PettyCashFundListView(ViewFinanceMixin, ListView):
    model = PettyCashFund
    template_name = "finance/petty_cash_fund_list.html"
    context_object_name = "funds"

    def get_queryset(self):
        return PettyCashFund.objects.select_related("custodian", "gl_account")


class PettyCashFundCreateView(EditFinanceMixin, CreateView):
    model = PettyCashFund
    form_class = PettyCashFundForm
    template_name = "finance/petty_cash_fund_form.html"
    success_url = reverse_lazy("finance:petty_cash_funds")

    def form_valid(self, form):
        messages.success(self.request, "Petty cash fund created.")
        return super().form_valid(form)


class PettyCashVoucherListView(ViewFinanceMixin, ListView):
    model = PettyCashVoucher
    template_name = "finance/petty_cash_voucher_list.html"
    context_object_name = "vouchers"
    paginate_by = 30

    def get_queryset(self):
        return PettyCashVoucher.objects.select_related("fund", "approved_by")


class PettyCashVoucherCreateView(EditFinanceMixin, CreateView):
    model = PettyCashVoucher
    form_class = PettyCashVoucherForm
    template_name = "finance/petty_cash_voucher_form.html"
    success_url = reverse_lazy("finance:petty_cash_vouchers")

    def form_valid(self, form):
        form.instance.approved_by = self.request.user
        response = super().form_valid(form)
        post_journal_for_petty_cash_voucher(self.object, user=self.request.user)
        messages.success(self.request, "Petty cash voucher recorded.")
        return response


class PettyCashReplenishView(EditFinanceMixin, View):
    template_name = "finance/petty_cash_replenish.html"

    def get(self, request, pk):
        fund = get_object_or_404(PettyCashFund, pk=pk)
        form = PettyCashReplenishForm(initial={"date": _today(), "amount": fund.float_amount})
        return render(request, self.template_name, {"fund": fund, "form": form})

    def post(self, request, pk):
        fund = get_object_or_404(PettyCashFund, pk=pk)
        form = PettyCashReplenishForm(request.POST)
        if form.is_valid():
            mapping = AccountMapping.get_solo()
            source_account = mapping.cash_account if form.cleaned_data["source"] == "cash" else mapping.mpesa_account
            if not source_account:
                messages.error(request, "Configure the Cash/M-Pesa account in Finance Settings first.")
            else:
                post_journal_for_petty_cash_replenishment(
                    fund, form.cleaned_data["amount"], form.cleaned_data["date"], source_account, user=request.user,
                )
                messages.success(request, f"Replenished {fund.name}.")
                return redirect(reverse("finance:petty_cash_funds"))
        return render(request, self.template_name, {"fund": fund, "form": form})


# ---------------------------------------------------------------------------
# Phase D: Accounts Payable + Accounts Receivable
# ---------------------------------------------------------------------------

class BillListView(ViewFinanceMixin, ListView):
    model = Bill
    template_name = "finance/bill_list.html"
    context_object_name = "bills"
    paginate_by = 30

    def get_queryset(self):
        return Bill.objects.select_related("supplier", "expense_account")


class BillCreateView(EditFinanceMixin, CreateView):
    model = Bill
    form_class = BillForm
    template_name = "finance/bill_form.html"
    success_url = reverse_lazy("finance:bills")

    def get_initial(self):
        initial = super().get_initial()
        purchase_id = self.request.GET.get("purchase")
        if purchase_id:
            from inventory.models import Purchase
            purchase = Purchase.objects.filter(pk=purchase_id).first()
            if purchase:
                initial.update({
                    "related_purchase": purchase.pk, "supplier": purchase.supplier_id,
                    "amount": purchase.total_cost, "bill_date": purchase.purchase_date,
                })

        order_id = self.request.GET.get("purchase_order")
        if order_id:
            from purchasing.models import PurchaseOrder
            order = PurchaseOrder.objects.filter(pk=order_id).first()
            if order:
                initial.update({
                    "supplier": order.supplier_id, "amount": order.total_amount, "bill_date": _today(),
                })
                self._purchase_order = order
        return initial

    def form_valid(self, form):
        if getattr(self, "_purchase_order", None):
            form.instance.related_purchase_order = self._purchase_order
        response = super().form_valid(form)
        sync_journal_for_bill(self.object, user=self.request.user)
        messages.success(self.request, "Bill recorded.")
        return response


class BillDetailView(ViewFinanceMixin, View):
    template_name = "finance/bill_detail.html"

    def get(self, request, pk):
        bill = get_object_or_404(Bill, pk=pk)
        return render(request, self.template_name, {"bill": bill, "form": BillPaymentForm(initial={"payment_date": _today()})})


class BillPaymentCreateView(EditFinanceMixin, View):
    def post(self, request, pk):
        bill = get_object_or_404(Bill, pk=pk)
        form = BillPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.bill = bill
            payment.save()
            post_journal_for_bill_payment(payment, user=request.user)
            bill.status = Bill.PAID if bill.balance_due <= 0 else Bill.PARTIAL
            bill.save(update_fields=["status"])
            messages.success(request, "Payment recorded.")
        else:
            messages.error(request, "Could not record that payment.")
        return redirect(reverse("finance:bill_detail", args=[pk]))


class BillDeleteView(EditFinanceMixin, DeleteView):
    model = Bill
    success_url = reverse_lazy("finance:bills")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("finance:bills")
        return ctx

    def form_valid(self, form):
        void_journal_for_bill(self.object, user=self.request.user)
        messages.success(self.request, "Bill deleted.")
        return super().form_valid(form)


class ARAgingView(ViewFinanceMixin, View):
    template_name = "finance/ar_aging.html"

    def get(self, request):
        from sales.models import Sale
        today = _today()
        buckets = {"0-30": [], "31-60": [], "61-90": [], "90+": []}
        totals = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
        sales = Sale.objects.filter(status__in=[Sale.UNPAID, Sale.UNRESOLVED])
        for sale in sales:
            age = (today - sale.date_created.date()).days
            if age <= 30:
                bucket = "0-30"
            elif age <= 60:
                bucket = "31-60"
            elif age <= 90:
                bucket = "61-90"
            else:
                bucket = "90+"
            buckets[bucket].append(sale)
            totals[bucket] += sale.amount

        if request.GET.get("export") == "xlsx":
            rows = []
            for bucket, sales_in_bucket in buckets.items():
                for sale in sales_in_bucket:
                    rows.append([sale.customer_name, sale.date_created.date().isoformat(), sale.amount, bucket])
            return build_xlsx(["Customer", "Date", "Amount", "Age Bucket"], rows, filename="ar_aging.xlsx")

        ctx = {"buckets": buckets, "totals": totals, "grand_total": round(sum(totals.values()), 2)}
        return render(request, self.template_name, ctx)


# ---------------------------------------------------------------------------
# Phase E: Budgeting
# ---------------------------------------------------------------------------

class BudgetListView(ViewFinanceMixin, ListView):
    model = Budget
    template_name = "finance/budget_list.html"
    context_object_name = "budgets"


class BudgetCreateView(EditFinanceMixin, View):
    template_name = "finance/budget_form.html"

    def get(self, request):
        form = BudgetForm()
        formset = BudgetLineFormSet()
        return render(request, self.template_name, {"form": form, "formset": formset})

    def post(self, request):
        form = BudgetForm(request.POST)
        formset = BudgetLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            budget = form.save()
            formset.instance = budget
            formset.save()
            messages.success(request, "Budget saved.")
            return redirect(reverse("finance:budgets"))
        return render(request, self.template_name, {"form": form, "formset": formset})


class BudgetVsActualView(ViewFinanceMixin, View):
    template_name = "finance/budget_vs_actual.html"

    def get(self, request, pk):
        budget = get_object_or_404(Budget, pk=pk)
        rows = []
        for line in budget.lines.select_related("account"):
            debit = JournalLine.objects.filter(
                account=line.account, entry__status=JournalEntry.POSTED,
                entry__date__gte=budget.period_start, entry__date__lte=budget.period_end,
            ).aggregate(total=Sum("debit"))["total"] or 0
            credit = JournalLine.objects.filter(
                account=line.account, entry__status=JournalEntry.POSTED,
                entry__date__gte=budget.period_start, entry__date__lte=budget.period_end,
            ).aggregate(total=Sum("credit"))["total"] or 0
            actual = (debit - credit) if line.account.normal_balance == "debit" else (credit - debit)
            rows.append({
                "account": line.account, "budgeted": line.budgeted_amount, "actual": round(actual, 2),
                "variance": round(line.budgeted_amount - actual, 2),
            })
        return render(request, self.template_name, {"budget": budget, "rows": rows})


# ---------------------------------------------------------------------------
# Phase F: Fixed Assets + Depreciation
# ---------------------------------------------------------------------------

class FixedAssetListView(ViewFinanceMixin, ListView):
    model = FixedAsset
    template_name = "finance/fixed_asset_list.html"
    context_object_name = "assets"

    def get_queryset(self):
        return FixedAsset.objects.select_related("asset_gl_account")


class FixedAssetCreateView(EditFinanceMixin, CreateView):
    model = FixedAsset
    form_class = FixedAssetForm
    template_name = "finance/fixed_asset_form.html"
    success_url = reverse_lazy("finance:fixed_assets")

    def form_valid(self, form):
        messages.success(self.request, "Fixed asset added.")
        return super().form_valid(form)


class RunDepreciationView(EditFinanceMixin, View):
    template_name = "finance/run_depreciation.html"

    def get(self, request):
        form = RunDepreciationForm(initial={"period": _today()})
        recent_entries = DepreciationEntry.objects.select_related("asset").order_by("-period", "-id")[:20]
        return render(request, self.template_name, {"form": form, "recent_entries": recent_entries})

    def post(self, request):
        form = RunDepreciationForm(request.POST)
        if form.is_valid():
            period = form.cleaned_data["period"].replace(day=1)
            entries, journal_entry = run_depreciation(period, user=request.user)
            if entries:
                messages.success(request, f"Posted depreciation for {len(entries)} asset(s) — {journal_entry.reference}.")
            else:
                messages.info(request, "Nothing to depreciate for that period (already run, or no eligible assets).")
            return redirect(reverse("finance:run_depreciation"))
        recent_entries = DepreciationEntry.objects.select_related("asset").order_by("-period", "-id")[:20]
        return render(request, self.template_name, {"form": form, "recent_entries": recent_entries})


# ---------------------------------------------------------------------------
# Phase G: Tax / VAT
# ---------------------------------------------------------------------------

class TaxRateListView(ViewFinanceMixin, ListView):
    model = TaxRate
    template_name = "finance/tax_rate_list.html"
    context_object_name = "tax_rates"


class TaxRateCreateView(EditFinanceMixin, CreateView):
    model = TaxRate
    form_class = TaxRateForm
    template_name = "finance/tax_rate_form.html"
    success_url = reverse_lazy("finance:tax_rates")

    def form_valid(self, form):
        messages.success(self.request, "Tax rate added.")
        return super().form_valid(form)


class VATReturnView(ViewFinanceMixin, View):
    template_name = "finance/vat_return.html"

    def get(self, request):
        today = _today()
        date_start = request.GET.get("date_start") or today.replace(day=1).isoformat()
        date_end = request.GET.get("date_end") or today.isoformat()

        mapping = AccountMapping.get_solo()
        output_vat = 0
        if mapping.vat_payable_account:
            output_vat = JournalLine.objects.filter(
                account=mapping.vat_payable_account, entry__status=JournalEntry.POSTED,
                entry__date__gte=date_start, entry__date__lte=date_end,
            ).aggregate(total=Sum("credit"))["total"] or 0

        input_vat = 0
        bills = Bill.objects.filter(bill_date__gte=date_start, bill_date__lte=date_end, tax_rate__isnull=False)
        for bill in bills:
            input_vat += bill.amount * bill.tax_rate.rate / (1 + bill.tax_rate.rate) if bill.tax_rate.rate else 0

        ctx = {
            "date_start": date_start, "date_end": date_end,
            "output_vat": round(output_vat, 2), "input_vat": round(input_vat, 2),
            "net_vat": round(output_vat - input_vat, 2),
        }
        return render(request, self.template_name, ctx)


# ---------------------------------------------------------------------------
# Phase H: Financial Statements
# ---------------------------------------------------------------------------

class IncomeStatementView(ViewFinanceMixin, View):
    template_name = "finance/income_statement.html"

    def get(self, request):
        today = _today()
        date_start = request.GET.get("date_start") or today.replace(day=1).isoformat()
        date_end = request.GET.get("date_end") or today.isoformat()

        income_rows, expense_rows = [], []
        total_income = total_expense = 0
        for account in Account.objects.filter(account_type=Account.INCOME, is_active=True):
            amount = _account_period_amount(account, date_start, date_end)
            if amount:
                income_rows.append({"account": account, "amount": amount})
                total_income += amount
        for account in Account.objects.filter(account_type=Account.EXPENSE, is_active=True):
            amount = _account_period_amount(account, date_start, date_end)
            if amount:
                expense_rows.append({"account": account, "amount": amount})
                total_expense += amount

        ctx = {
            "date_start": date_start, "date_end": date_end,
            "income_rows": income_rows, "expense_rows": expense_rows,
            "total_income": round(total_income, 2), "total_expense": round(total_expense, 2),
            "net_income": round(total_income - total_expense, 2),
        }
        return render(request, self.template_name, ctx)


class BalanceSheetView(ViewFinanceMixin, View):
    template_name = "finance/balance_sheet.html"

    def get(self, request):
        as_of = request.GET.get("as_of") or _today().isoformat()

        asset_rows, liability_rows, equity_rows = [], [], []
        total_assets = total_liabilities = total_equity = 0
        for account in Account.objects.filter(account_type=Account.ASSET, is_active=True):
            balance = account.balance_as_of(as_of)
            if balance:
                asset_rows.append({"account": account, "amount": balance})
                total_assets += balance
        for account in Account.objects.filter(account_type=Account.LIABILITY, is_active=True):
            balance = account.balance_as_of(as_of)
            if balance:
                liability_rows.append({"account": account, "amount": balance})
                total_liabilities += balance
        for account in Account.objects.filter(account_type=Account.EQUITY, is_active=True):
            balance = account.balance_as_of(as_of)
            if balance:
                equity_rows.append({"account": account, "amount": balance})
                total_equity += balance

        retained_earnings = _cumulative_net_income(as_of)
        total_equity += retained_earnings

        ctx = {
            "as_of": as_of, "asset_rows": asset_rows, "liability_rows": liability_rows,
            "equity_rows": equity_rows, "retained_earnings": round(retained_earnings, 2),
            "total_assets": round(total_assets, 2), "total_liabilities": round(total_liabilities, 2),
            "total_equity": round(total_equity, 2),
            "total_liabilities_and_equity": round(total_liabilities + total_equity, 2),
        }
        return render(request, self.template_name, ctx)


def _account_period_amount(account, date_start, date_end):
    lines = JournalLine.objects.filter(
        account=account, entry__status=JournalEntry.POSTED,
        entry__date__gte=date_start, entry__date__lte=date_end,
    )
    totals = lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    debit, credit = totals["debit"] or 0, totals["credit"] or 0
    if account.normal_balance == "debit":
        return round(debit - credit, 2)
    return round(credit - debit, 2)


def _cumulative_net_income(as_of):
    """Live Retained Earnings — cumulative net income to date. There's no period-close
    process in v1, so this is computed on the fly rather than maintained as a ledger
    balance."""
    income = 0
    for account in Account.objects.filter(account_type=Account.INCOME, is_active=True):
        income += _account_period_amount(account, "1900-01-01", as_of)
    expense = 0
    for account in Account.objects.filter(account_type=Account.EXPENSE, is_active=True):
        expense += _account_period_amount(account, "1900-01-01", as_of)
    return round(income - expense, 2)
