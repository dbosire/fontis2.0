from django import forms
from django.forms import inlineformset_factory

from .models import Sale, SaleItem

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ["customer_name", "type", "delivery_address", "status", "comments"]
        widgets = {
            "customer_name": forms.TextInput(
                attrs={"class": TEXT_INPUT, "list": "customer-options", "autocomplete": "off"}
            ),
            "type": forms.Select(attrs={"class": TEXT_INPUT}),
            "delivery_address": forms.TextInput(attrs={"class": TEXT_INPUT}),
            "status": forms.Select(attrs={"class": TEXT_INPUT}),
            "comments": forms.Textarea(attrs={"class": TEXT_INPUT, "rows": 2}),
        }


class SaleItemForm(forms.ModelForm):
    quantity = forms.FloatField(
        initial=1,
        min_value=0.01,
        widget=forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01", "min": "0.01"}),
    )

    class Meta:
        model = SaleItem
        fields = ["jar_type", "quantity", "price"]
        widgets = {
            "jar_type": forms.Select(attrs={"class": TEXT_INPUT}),
            "price": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01", "min": "0"}),
        }


SaleItemFormSet = inlineformset_factory(
    Sale, SaleItem, form=SaleItemForm, extra=1, can_delete=True, min_num=1, validate_min=True
)
