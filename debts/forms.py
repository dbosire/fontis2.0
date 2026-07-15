from django import forms

from .models import DebtPayment

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
