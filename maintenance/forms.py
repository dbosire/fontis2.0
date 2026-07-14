from django import forms
from django.forms import inlineformset_factory

from .models import JarType, JarTypeMaterial

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"


class JarTypeForm(forms.ModelForm):
    has_stock = forms.BooleanField(
        required=False, label="Track stock", widget=forms.CheckboxInput(attrs={"class": "rounded border-gray-300"})
    )

    class Meta:
        model = JarType
        fields = ["name", "description", "pricing", "has_stock", "stock", "volume_value", "volume_unit"]
        widgets = {
            "name": forms.TextInput(attrs={"class": TEXT_INPUT}),
            "description": forms.Textarea(attrs={"class": TEXT_INPUT, "rows": 3}),
            "pricing": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01"}),
            "has_stock": forms.CheckboxInput(attrs={"class": "rounded border-gray-300"}),
            "stock": forms.NumberInput(attrs={"class": TEXT_INPUT}),
            "volume_value": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01", "min": "0"}),
            "volume_unit": forms.Select(attrs={"class": TEXT_INPUT}),
        }

    def clean_has_stock(self):
        return "1" if self.cleaned_data.get("has_stock") else None


class JarTypeMaterialForm(forms.ModelForm):
    class Meta:
        model = JarTypeMaterial
        fields = ["material", "quantity_per_sale"]
        widgets = {
            "material": forms.Select(attrs={"class": TEXT_INPUT}),
            "quantity_per_sale": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01", "min": "0.01"}),
        }


JarTypeMaterialFormSet = inlineformset_factory(
    JarType, JarTypeMaterial, form=JarTypeMaterialForm, extra=1, can_delete=True
)
