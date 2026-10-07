from django import forms

from employees.models import Employee

from .models import (
    Calibration, ComplianceDocument, Equipment, MedicalCertificate, PersonnelDocument, Procedure,
    PremisesRequirement,
)

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
FILE_INPUT = "block w-full text-sm text-gray-600 dark:text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
CHECKBOX = "rounded border-gray-300"


def _widgets(*fields, kind="text"):
    widget_cls = {
        "text": forms.TextInput, "textarea": forms.Textarea, "select": forms.Select,
        "number": forms.NumberInput, "date": forms.DateInput,
    }[kind]
    attrs = {"class": TEXT_INPUT}
    if kind == "date":
        attrs["type"] = "date"
    if kind == "textarea":
        attrs["rows"] = 3
    return {f: widget_cls(attrs=attrs, **({"format": "%Y-%m-%d"} if kind == "date" else {})) for f in fields}


def _file_widget():
    # Plain FileInput rather than ClearableFileInput: the latter renders a link to
    # file.url, and these files are intentionally not publicly URL-addressable.
    return forms.FileInput(attrs={"class": FILE_INPUT})


class ComplianceDocumentForm(forms.ModelForm):
    class Meta:
        model = ComplianceDocument
        fields = ["category", "title", "reference_number", "issuing_authority", "issue_date", "expiry_date", "file", "notes"]
        widgets = {
            **_widgets("category", kind="select"),
            **_widgets("title", "reference_number", "issuing_authority"),
            **_widgets("issue_date", "expiry_date", kind="date"),
            **_widgets("notes", kind="textarea"),
            "file": _file_widget(),
        }

    def clean(self):
        cleaned = super().clean()
        issued, expiry = cleaned.get("issue_date"), cleaned.get("expiry_date")
        if issued and expiry and expiry < issued:
            self.add_error("expiry_date", "Expiry date can't be before the issue date.")
        return cleaned


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = ["name", "serial_number", "location", "is_active", "notes"]
        widgets = {
            **_widgets("name", "serial_number", "location"),
            **_widgets("notes", kind="textarea"),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX}),
        }


class CalibrationForm(forms.ModelForm):
    class Meta:
        model = Calibration
        fields = ["calibration_date", "next_due_date", "certificate_number", "calibrated_by", "file", "notes"]
        widgets = {
            **_widgets("calibration_date", "next_due_date", kind="date"),
            **_widgets("certificate_number", "calibrated_by"),
            **_widgets("notes", kind="textarea"),
            "file": _file_widget(),
        }

    def clean(self):
        cleaned = super().clean()
        done, due = cleaned.get("calibration_date"), cleaned.get("next_due_date")
        if done and due and due <= done:
            self.add_error("next_due_date", "Next due date must be after the calibration date.")
        return cleaned


class MedicalCertificateForm(forms.ModelForm):
    class Meta:
        model = MedicalCertificate
        fields = ["employee", "certificate_number", "issued_date", "expiry_date", "issuing_facility", "file", "notes"]
        widgets = {
            **_widgets("employee", kind="select"),
            **_widgets("certificate_number", "issuing_facility"),
            **_widgets("issued_date", "expiry_date", kind="date"),
            **_widgets("notes", kind="textarea"),
            "file": _file_widget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(status=Employee.ACTIVE)

    def clean(self):
        cleaned = super().clean()
        issued, expiry = cleaned.get("issued_date"), cleaned.get("expiry_date")
        if issued and expiry and expiry <= issued:
            self.add_error("expiry_date", "Expiry date must be after the issue date.")
        return cleaned


class PersonnelDocumentForm(forms.ModelForm):
    class Meta:
        model = PersonnelDocument
        fields = ["employee", "doc_type", "title", "institution", "date_obtained", "file", "notes"]
        widgets = {
            **_widgets("employee", "doc_type", kind="select"),
            **_widgets("title", "institution"),
            **_widgets("date_obtained", kind="date"),
            **_widgets("notes", kind="textarea"),
            "file": _file_widget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(status=Employee.ACTIVE)


class ProcedureForm(forms.ModelForm):
    class Meta:
        model = Procedure
        fields = ["code", "title", "category", "version", "owner", "effective_date", "next_review_date", "content"]
        widgets = {
            **_widgets("code", "title", "version", "owner"),
            **_widgets("category", kind="select"),
            **_widgets("effective_date", "next_review_date", kind="date"),
            "content": forms.Textarea(attrs={"class": TEXT_INPUT + " font-mono", "rows": 28}),
        }


class PremisesRequirementForm(forms.ModelForm):
    class Meta:
        model = PremisesRequirement
        fields = ["is_met", "notes"]
        widgets = {
            "is_met": forms.CheckboxInput(attrs={"class": CHECKBOX}),
            "notes": forms.TextInput(attrs={"class": TEXT_INPUT, "placeholder": "Notes (optional)"}),
        }
