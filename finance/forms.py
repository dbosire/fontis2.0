from django import forms
from django.forms import inlineformset_factory

from expenses.models import ExpenseCategory
from .models import (
    Account, AccountMapping, BankAccount, BankStatementLine, Bill, BillPayment,
    Budget, BudgetLine, ExpenseCategoryAccountMapping, FixedAsset, JournalEntry,
    JournalLine, PettyCashFund, PettyCashVoucher, TaxRate,
)

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"


def _widgets(*fields, kind="text"):
    widget_cls = {
        "text": forms.TextInput, "textarea": forms.Textarea, "select": forms.Select,
        "number": forms.NumberInput, "date": forms.DateInput, "checkbox": forms.CheckboxInput,
    }[kind]
    attrs = {"class": TEXT_INPUT}
    if kind == "date":
        attrs["type"] = "date"
    if kind == "checkbox":
        attrs = {"class": "rounded border-gray-300"}
    return {f: widget_cls(attrs=attrs) for f in fields}


def _expense_category_field():
    # Sourced live from ExpenseCategory — see expenses.forms.ExpenseForm for why.
    return forms.ChoiceField(
        choices=[(c.name, c.name) for c in ExpenseCategory.objects.all()],
        widget=forms.Select(attrs={"class": TEXT_INPUT}),
    )


# ---------------------------------------------------------------------------
# Phase A: Chart of Accounts + manual journal entries
# ---------------------------------------------------------------------------

class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["code", "name", "account_type", "parent", "is_cash_account", "is_active", "description"]
        widgets = {
            **_widgets("code", "name"),
            **_widgets("account_type", "parent", kind="select"),
            **_widgets("is_cash_account", "is_active", kind="checkbox"),
            **_widgets("description", kind="textarea"),
        }


class JournalEntryForm(forms.ModelForm):
    class Meta:
        model = JournalEntry
        fields = ["date", "description"]
        widgets = {**_widgets("date", kind="date"), **_widgets("description")}


class JournalLineForm(forms.ModelForm):
    class Meta:
        model = JournalLine
        fields = ["account", "debit", "credit", "description"]
        widgets = {
            **_widgets("account", kind="select"),
            **_widgets("debit", "credit", kind="number"),
            **_widgets("description"),
        }


JournalLineFormSet = inlineformset_factory(
    JournalEntry, JournalLine, form=JournalLineForm, extra=0, can_delete=True, min_num=2, validate_min=True
)


# ---------------------------------------------------------------------------
# Phase B: account mapping
# ---------------------------------------------------------------------------

class AccountMappingForm(forms.ModelForm):
    class Meta:
        model = AccountMapping
        fields = [
            "cash_account", "mpesa_account", "accounts_receivable_account", "sales_revenue_account",
            "accounts_payable_account", "default_expense_account", "salaries_expense_account",
            "employee_advances_account", "payroll_deductions_payable_account",
            "vat_payable_account", "vat_receivable_account",
        ]
        widgets = _widgets(*fields, kind="select")


class ExpenseCategoryAccountMappingForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategoryAccountMapping
        fields = ["category", "account"]
        widgets = _widgets("account", kind="select")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"] = _expense_category_field()


# ---------------------------------------------------------------------------
# Phase C: bank reconciliation + petty cash
# ---------------------------------------------------------------------------

class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ["name", "account_number", "gl_account"]
        widgets = {**_widgets("name", "account_number"), **_widgets("gl_account", kind="select")}


class BankStatementLineForm(forms.ModelForm):
    class Meta:
        model = BankStatementLine
        fields = ["date", "description", "amount"]
        widgets = {**_widgets("date", kind="date"), **_widgets("description"), **_widgets("amount", kind="number")}


class PettyCashFundForm(forms.ModelForm):
    class Meta:
        model = PettyCashFund
        fields = ["name", "custodian", "gl_account", "float_amount"]
        widgets = {
            **_widgets("name"),
            **_widgets("custodian", "gl_account", kind="select"),
            **_widgets("float_amount", kind="number"),
        }


class PettyCashVoucherForm(forms.ModelForm):
    class Meta:
        model = PettyCashVoucher
        fields = ["fund", "date", "description", "amount", "category"]
        widgets = {
            **_widgets("fund", kind="select"),
            **_widgets("date", kind="date"),
            **_widgets("description"),
            **_widgets("amount", kind="number"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"] = _expense_category_field()


class PettyCashReplenishForm(forms.Form):
    amount = forms.FloatField(widget=forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01", "min": "0.01"}))
    date = forms.DateField(widget=forms.DateInput(attrs={"class": TEXT_INPUT, "type": "date"}))
    source = forms.ChoiceField(
        choices=[("cash", "Cash"), ("mpesa", "M-Pesa")], widget=forms.Select(attrs={"class": TEXT_INPUT})
    )


# ---------------------------------------------------------------------------
# Phase D: Accounts Payable
# ---------------------------------------------------------------------------

class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = [
            "supplier", "related_purchase", "expense_account", "tax_rate",
            "bill_number", "bill_date", "due_date", "amount", "notes",
        ]
        widgets = {
            **_widgets("supplier", "related_purchase", "expense_account", "tax_rate", kind="select"),
            **_widgets("bill_number"),
            **_widgets("bill_date", "due_date", kind="date"),
            **_widgets("amount", kind="number"),
            **_widgets("notes", kind="textarea"),
        }


class BillPaymentForm(forms.ModelForm):
    class Meta:
        model = BillPayment
        fields = ["amount", "payment_date", "payment_method", "notes"]
        widgets = {
            **_widgets("amount", kind="number"),
            **_widgets("payment_date", kind="date"),
            **_widgets("payment_method", kind="select"),
            **_widgets("notes"),
        }


# ---------------------------------------------------------------------------
# Phase E: Budgeting
# ---------------------------------------------------------------------------

class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["name", "period_start", "period_end", "is_active"]
        widgets = {
            **_widgets("name"),
            **_widgets("period_start", "period_end", kind="date"),
            **_widgets("is_active", kind="checkbox"),
        }


class BudgetLineForm(forms.ModelForm):
    class Meta:
        model = BudgetLine
        fields = ["account", "budgeted_amount"]
        widgets = {**_widgets("account", kind="select"), **_widgets("budgeted_amount", kind="number")}


BudgetLineFormSet = inlineformset_factory(
    Budget, BudgetLine, form=BudgetLineForm, extra=3, can_delete=True
)


# ---------------------------------------------------------------------------
# Phase F: Fixed Assets
# ---------------------------------------------------------------------------

class FixedAssetForm(forms.ModelForm):
    class Meta:
        model = FixedAsset
        fields = [
            "name", "category", "purchase_date", "cost", "salvage_value", "useful_life_years",
            "depreciation_method", "asset_gl_account", "depreciation_expense_account",
            "accumulated_depreciation_account",
        ]
        widgets = {
            **_widgets("name", "category"),
            **_widgets("purchase_date", kind="date"),
            **_widgets("cost", "salvage_value", "useful_life_years", kind="number"),
            **_widgets(
                "depreciation_method", "asset_gl_account", "depreciation_expense_account",
                "accumulated_depreciation_account", kind="select",
            ),
        }


class RunDepreciationForm(forms.Form):
    period = forms.DateField(
        widget=forms.DateInput(attrs={"class": TEXT_INPUT, "type": "date"}),
        help_text="Any date within the month to run depreciation for — it's normalized to the 1st.",
    )


# ---------------------------------------------------------------------------
# Phase G: Tax / VAT
# ---------------------------------------------------------------------------

class TaxRateForm(forms.ModelForm):
    class Meta:
        model = TaxRate
        fields = ["name", "rate", "is_default"]
        widgets = {**_widgets("name"), **_widgets("rate", kind="number"), **_widgets("is_default", kind="checkbox")}
