from django import forms

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"


class SystemInfoForm(forms.Form):
    name = forms.CharField(widget=forms.TextInput(attrs={"class": TEXT_INPUT}))
    short_name = forms.CharField(widget=forms.TextInput(attrs={"class": TEXT_INPUT}))
    logo = forms.ImageField(required=False)
    cover = forms.ImageField(required=False)
