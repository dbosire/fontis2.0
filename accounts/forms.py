from django import forms
from django.contrib.auth.forms import AuthenticationForm

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
