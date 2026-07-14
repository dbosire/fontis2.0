from django import forms

from .models import Expense, ExpenseCategory

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["expense_name", "category", "amount", "date_created", "status", "employee"]
        widgets = {
            "expense_name": forms.TextInput(attrs={"class": TEXT_INPUT}),
            "amount": forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01"}),
            "date_created": forms.DateTimeInput(attrs={"class": TEXT_INPUT, "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "status": forms.Select(attrs={"class": TEXT_INPUT}),
            "employee": forms.Select(attrs={"class": TEXT_INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sourced live from ExpenseCategory rather than a frozen model-level choices
        # list, so a category added via Expenses > Categories shows up immediately.
        self.fields["category"] = forms.ChoiceField(
            choices=[(c.name, c.name) for c in ExpenseCategory.objects.all()],
            widget=forms.Select(attrs={"class": TEXT_INPUT}),
        )


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": TEXT_INPUT, "placeholder": "e.g. Fuel"})}
