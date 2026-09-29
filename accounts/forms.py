from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q

from .models import User

TEXT_INPUT_CLASSES = (
    "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm "
    "focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
)

# Distinct from TEXT_INPUT_CLASSES — the login page sits on a glassmorphism card, not
# the app's normal white-card chrome, so its inputs need their own light/dark-aware
# styling rather than the shared one ProfileForm/SetNewPasswordForm use.
LOGIN_INPUT_CLASSES = (
    "block w-full rounded-lg border border-gray-300/80 dark:border-white/10 "
    "bg-white/80 dark:bg-slate-800/60 px-4 py-2.5 text-base text-gray-900 dark:text-white "
    "placeholder-gray-400 dark:placeholder-blue-200/40 "
    "focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors"
)


class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = LOGIN_INPUT_CLASSES


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["firstname", "lastname", "username", "avatar"]
        widgets = {
            "firstname": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "lastname": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "username": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
        }


class UserForm(forms.ModelForm):
    """Shared by create and edit — never carries a password field. A new user gets
    an auto-generated temporary password (see accounts/views.py::UserCreateView,
    matching accounts/management/commands/reset_all_passwords.py's own philosophy
    of never letting an admin silently set a password the user themselves never
    sees); resetting one later is its own dedicated action, not a field buried in
    this form."""

    employee = forms.ModelChoiceField(
        queryset=None, required=False,
        help_text="Optionally link this login to an employee record.",
        widget=forms.Select(attrs={"class": TEXT_INPUT_CLASSES}),
    )

    class Meta:
        model = User
        fields = ["username", "firstname", "lastname", "is_active", "is_superuser"]
        widgets = {
            "username": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "firstname": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "lastname": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from employees.models import Employee

        # An employee already linked to a DIFFERENT user must stay out of the
        # choices (one login per employee) — except the one already linked to
        # *this* user being edited, which needs to remain selectable/pre-filled.
        current = self.instance.employee if self.instance.pk and hasattr(self.instance, "employee") else None
        qs = Employee.objects.filter(Q(user__isnull=True) | Q(pk=current.pk if current else None))
        self.fields["employee"].queryset = qs.order_by("first_name", "last_name")
        if current:
            self.fields["employee"].initial = current.pk


class SetNewPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        label="New password", widget=forms.PasswordInput(attrs={"class": TEXT_INPUT_CLASSES})
    )
    new_password2 = forms.CharField(
        label="Confirm new password", widget=forms.PasswordInput(attrs={"class": TEXT_INPUT_CLASSES})
    )

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("new_password1"), cleaned.get("new_password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned
