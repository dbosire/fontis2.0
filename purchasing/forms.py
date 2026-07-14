from django import forms
from django.forms import inlineformset_factory

from .models import (
    PurchaseOrder, PurchaseOrderLine, PurchaseRequest, PurchaseRequestLine,
)

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


class PurchaseRequestForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = ["department", "needed_by_date", "notes"]
        widgets = {
            **_widgets("department", kind="select"),
            **_widgets("needed_by_date", kind="date"),
            **_widgets("notes", kind="textarea"),
        }


class PurchaseRequestLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequestLine
        fields = ["material", "quantity", "notes"]
        widgets = {
            **_widgets("material", kind="select"),
            **_widgets("quantity", kind="number"),
            **_widgets("notes"),
        }


PurchaseRequestLineFormSet = inlineformset_factory(
    PurchaseRequest, PurchaseRequestLine, form=PurchaseRequestLineForm,
    extra=0, min_num=1, validate_min=True, can_delete=True,
)


class PurchaseRequestRejectForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": TEXT_INPUT, "rows": 2}), required=False,
    )


class PurchaseOrderFromRequestForm(forms.Form):
    supplier = forms.ModelChoiceField(
        queryset=None, widget=forms.Select(attrs={"class": TEXT_INPUT}),
    )
    order_date = forms.DateField(widget=forms.DateInput(attrs={"class": TEXT_INPUT, "type": "date"}))
    expected_delivery_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"class": TEXT_INPUT, "type": "date"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from inventory.models import Supplier
        self.fields["supplier"].queryset = Supplier.objects.all()


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "order_date", "expected_delivery_date", "notes"]
        widgets = {
            **_widgets("supplier", kind="select"),
            **_widgets("order_date", "expected_delivery_date", kind="date"),
            **_widgets("notes", kind="textarea"),
        }


class PurchaseOrderLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderLine
        fields = ["material", "quantity_ordered", "unit_price"]
        widgets = {
            **_widgets("material", kind="select"),
            **_widgets("quantity_ordered", "unit_price", kind="number"),
        }


PurchaseOrderLineFormSet = inlineformset_factory(
    PurchaseOrder, PurchaseOrderLine, form=PurchaseOrderLineForm,
    extra=0, min_num=1, validate_min=True, can_delete=True,
)


class GoodsReceiptForm(forms.Form):
    receipt_date = forms.DateField(widget=forms.DateInput(attrs={"class": TEXT_INPUT, "type": "date"}))
    received_by = forms.ModelChoiceField(queryset=None, required=False, widget=forms.Select(attrs={"class": TEXT_INPUT}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": TEXT_INPUT, "rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from employees.models import Employee
        self.fields["received_by"].queryset = Employee.objects.all()
