from django import forms

from .models import DailyReconciliation

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


class DailyReconciliationForm(forms.ModelForm):
    class Meta:
        model = DailyReconciliation
        fields = ["date", "cash_collected", "notes"]
        widgets = {
            **_widgets("date", kind="date"),
            **_widgets("cash_collected", kind="number"),
            **_widgets("notes", kind="textarea"),
        }
