from django import forms
from django.forms import inlineformset_factory

from .models import (
    Attendance, Department, Employee, EmployeeAsset, LeaveRequest, Payroll,
    PerformanceReview, Role, RolePermission, TrainingProgram, TrainingRecord,
)

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"


def _widgets(*fields, kind="text"):
    widget_cls = {
        "text": forms.TextInput, "textarea": forms.Textarea, "select": forms.Select,
        "number": forms.NumberInput, "date": forms.DateInput, "time": forms.TimeInput,
        "email": forms.EmailInput,
    }[kind]
    attrs = {"class": TEXT_INPUT}
    if kind == "date":
        attrs["type"] = "date"
    if kind == "time":
        attrs["type"] = "time"
    return {f: widget_cls(attrs=attrs) for f in fields}


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "description"]
        widgets = {**_widgets("name"), **_widgets("description", kind="textarea")}


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ["name", "department", "description"]
        widgets = {**_widgets("name"), **_widgets("department", kind="select"), **_widgets("description", kind="textarea")}


class RolePermissionForm(forms.ModelForm):
    class Meta:
        model = RolePermission
        fields = ["module", "can_view", "can_edit"]
        widgets = {
            "module": forms.Select(attrs={"class": TEXT_INPUT}),
            "can_view": forms.CheckboxInput(attrs={"class": "rounded border-gray-300"}),
            "can_edit": forms.CheckboxInput(attrs={"class": "rounded border-gray-300"}),
        }


RolePermissionFormSet = inlineformset_factory(
    Role, RolePermission, form=RolePermissionForm, extra=1, can_delete=True
)


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "employee_number", "first_name", "last_name", "gender", "date_of_birth", "id_number",
            "phone", "email", "address", "department", "role", "employment_type", "date_hired",
            "date_terminated", "status", "basic_salary", "bank_name", "bank_account_number",
            "kra_pin", "nssf_number", "nhif_number", "emergency_contact_name", "emergency_contact_phone",
        ]
        widgets = {
            **_widgets("employee_number", "first_name", "last_name", "id_number", "phone", "address",
                       "bank_name", "bank_account_number", "kra_pin", "nssf_number", "nhif_number",
                       "emergency_contact_name", "emergency_contact_phone"),
            **_widgets("email", kind="email"),
            **_widgets("gender", "department", "role", "employment_type", "status", kind="select"),
            **_widgets("date_of_birth", "date_hired", "date_terminated", kind="date"),
            **_widgets("basic_salary", kind="number"),
        }


class EmployeeAssetForm(forms.ModelForm):
    class Meta:
        model = EmployeeAsset
        fields = ["employee", "item_name", "category", "issued_date", "returned_date", "status", "notes"]
        widgets = {
            **_widgets("employee", "status", kind="select"),
            **_widgets("item_name", "category"),
            **_widgets("issued_date", "returned_date", kind="date"),
            **_widgets("notes", kind="textarea"),
        }


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ["employee", "date", "check_in", "check_out", "status", "notes"]
        widgets = {
            **_widgets("employee", "status", kind="select"),
            **_widgets("date", kind="date"),
            **_widgets("check_in", "check_out", kind="time"),
            **_widgets("notes"),
        }


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["employee", "leave_type", "start_date", "end_date", "reason"]
        widgets = {
            **_widgets("employee", "leave_type", kind="select"),
            **_widgets("start_date", "end_date", kind="date"),
            **_widgets("reason", kind="textarea"),
        }


class PayrollForm(forms.ModelForm):
    class Meta:
        model = Payroll
        fields = ["employee", "period_start", "period_end", "basic_salary", "other_deductions", "allowances", "notes"]
        widgets = {
            **_widgets("employee", kind="select"),
            **_widgets("period_start", "period_end", kind="date"),
            **_widgets("basic_salary", "other_deductions", "allowances", kind="number"),
            **_widgets("notes", kind="textarea"),
        }


class PerformanceReviewForm(forms.ModelForm):
    class Meta:
        model = PerformanceReview
        fields = ["employee", "review_period", "rating", "comments", "goals"]
        widgets = {
            **_widgets("employee", "rating", kind="select"),
            **_widgets("review_period"),
            **_widgets("comments", "goals", kind="textarea"),
        }


class TrainingProgramForm(forms.ModelForm):
    class Meta:
        model = TrainingProgram
        fields = ["name", "description", "provider", "duration_days"]
        widgets = {
            **_widgets("name", "provider"),
            **_widgets("description", kind="textarea"),
            **_widgets("duration_days", kind="number"),
        }


class TrainingRecordForm(forms.ModelForm):
    class Meta:
        model = TrainingRecord
        fields = ["employee", "program", "start_date", "completion_date", "status", "certificate_expiry", "notes"]
        widgets = {
            **_widgets("employee", "program", "status", kind="select"),
            **_widgets("start_date", "completion_date", "certificate_expiry", kind="date"),
            **_widgets("notes", kind="textarea"),
        }
