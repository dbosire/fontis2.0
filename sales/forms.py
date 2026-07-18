from django import forms
from django.forms import inlineformset_factory

from debts.models import DebtPayment

from .models import Sale, SaleItem

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"


class SaleForm(forms.ModelForm):
    # Not real Sale fields — only used when status is newly set to Partially Paid,
    # to record the initial DebtPayment so the balance is actually tracked as a debt
    # (see SaleFormView.post()) instead of the status label just sitting there with
    # nothing behind it, the same gap the Credit status had before it was fixed.
    amount_paid_now = forms.FloatField(
        required=False, min_value=0.01,
        widget=forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01", "min": "0.01"}),
        help_text="The remaining balance will be tracked as a debt.",
    )
    payment_method_now = forms.ChoiceField(
        required=False, choices=[(DebtPayment.CASH, "Cash"), (DebtPayment.MPESA, "M-Pesa")],
        initial=DebtPayment.CASH, widget=forms.Select(attrs={"class": TEXT_INPUT}),
    )

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

    def clean(self):
        cleaned = super().clean()
        # self.instance.status is still the pre-edit value here — construct_instance()
        # (which overwrites it with the submitted value) only runs after clean().
        old_status = self.instance.status
        if cleaned.get("status") == Sale.PARTIAL and old_status != Sale.PARTIAL and not cleaned.get("amount_paid_now"):
            self.add_error("amount_paid_now", "Enter the amount already paid.")
        return cleaned


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
