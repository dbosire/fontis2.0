from django import forms

from .models import Purchase, RawMaterial, Supplier

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"


class RawMaterialForm(forms.ModelForm):
    class Meta:
        model = RawMaterial
        fields = ["name", "category", "unit", "current_stock", "reorder_level", "default_supplier", "unit_cost", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": TEXT_INPUT}),
            "category": forms.Select(attrs={"class": TEXT_INPUT}),
            "unit": forms.Select(attrs={"class": TEXT_INPUT}),
            "current_stock": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01", "min": "0"}),
            "reorder_level": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01", "min": "0"}),
            "default_supplier": forms.Select(attrs={"class": TEXT_INPUT}),
            "unit_cost": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01", "min": "0"}),
            "notes": forms.Textarea(attrs={"class": TEXT_INPUT, "rows": 2}),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "phone", "email", "address", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": TEXT_INPUT}),
            "phone": forms.TextInput(attrs={"class": TEXT_INPUT}),
            "email": forms.EmailInput(attrs={"class": TEXT_INPUT}),
            "address": forms.Textarea(attrs={"class": TEXT_INPUT, "rows": 2}),
            "notes": forms.Textarea(attrs={"class": TEXT_INPUT, "rows": 2}),
        }


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ["material", "supplier", "quantity", "unit_cost", "purchase_date", "expiry_date", "notes"]
        widgets = {
            "material": forms.Select(attrs={"class": TEXT_INPUT}),
            "supplier": forms.Select(attrs={"class": TEXT_INPUT}),
            "quantity": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01", "min": "0.01"}),
            "unit_cost": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01", "min": "0"}),
            "purchase_date": forms.DateInput(attrs={"class": TEXT_INPUT, "type": "date"}),
            "expiry_date": forms.DateInput(attrs={"class": TEXT_INPUT, "type": "date"}),
            "notes": forms.Textarea(attrs={"class": TEXT_INPUT, "rows": 2}),
        }
