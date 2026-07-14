from django import forms

from .models import LabTest

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"


class LabTestForm(forms.ModelForm):
    class Meta:
        model = LabTest
        fields = ["sample_name", "technician", "date_created", "tds", "ec", "ph", "salinity", "temperature"]
        widgets = {
            "sample_name": forms.TextInput(attrs={"class": TEXT_INPUT}),
            "technician": forms.Select(attrs={"class": TEXT_INPUT}),
            "date_created": forms.DateTimeInput(attrs={"class": TEXT_INPUT, "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "tds": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01"}),
            "ec": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01"}),
            "ph": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01"}),
            "salinity": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01"}),
            "temperature": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01"}),
        }
