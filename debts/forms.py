from django import forms

from .models import CustomerCredit, DebtPayment

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"


def _widgets(*fields, kind="text"):
    widget_cls = {
        "text": forms.TextInput, "textarea": forms.Textarea, "select": forms.Select,
        "number": forms.NumberInput, "date": forms.DateInput,
    }[kind]
    attrs = {"class": TEXT_INPUT}
    if kind == "date":
        attrs["type"] = "date"
    return {f: widget_cls(attrs=attrs) for f in fields}


class DebtPaymentForm(forms.ModelForm):
    class Meta:
        model = DebtPayment
        fields = ["amount", "payment_date", "payment_method", "notes"]
        widgets = {
            **_widgets("amount", kind="number"),
            **_widgets("payment_date", kind="date"),
            **_widgets("payment_method", kind="select"),
            **_widgets("notes"),
        }


class PrepaymentForm(forms.ModelForm):
    customer_name = forms.CharField(
        max_length=255, widget=forms.TextInput(attrs={"class": TEXT_INPUT, "list": "customer-options", "autocomplete": "off"}),
    )

    class Meta:
        model = CustomerCredit
        fields = ["customer_name", "amount", "payment_date", "payment_method", "notes"]
        widgets = {
            **_widgets("amount", kind="number"),
            **_widgets("payment_date", kind="date"),
            **_widgets("payment_method", kind="select"),
            **_widgets("notes"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cash/M-Pesa only — a prepayment can't itself be paid "via credit", that's
        # circular. CustomerCredit.payment_method's own choices already exclude
        # DebtPayment.CREDIT (see debts/models.py), this just keeps the field required
        # since the model field allows blank for APPLIED-source rows.
        self.fields["payment_method"].required = True
        # The model field's help_text describes the ledger in general (signed amount,
        # positive or negative) — on this form the amount is always a positive
        # prepayment, so swap in wording that matches what's actually being entered.
        self.fields["amount"].help_text = "How much this customer paid in advance."
