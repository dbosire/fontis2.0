from django import forms

from contacts.models import Contact
from .models import (
    Complaint, CustomerLoyalty, Feedback, FollowUp, LoyaltyProgram,
    LoyaltyTransaction, Promotion,
)

TEXT_INPUT = "block w-full rounded-md border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-white px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"


def _widgets(*fields, kind="text"):
    widget_cls = {
        "text": forms.TextInput, "textarea": forms.Textarea, "select": forms.Select,
        "number": forms.NumberInput, "date": forms.DateInput, "email": forms.EmailInput,
        "checkbox": forms.CheckboxInput,
    }[kind]
    attrs = {"class": TEXT_INPUT}
    if kind == "date":
        attrs["type"] = "date"
    if kind == "checkbox":
        attrs = {"class": "rounded border-gray-300"}
    return {f: widget_cls(attrs=attrs) for f in fields}


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = [
            "contact", "customer_name", "phone", "category", "subject", "description",
            "priority", "status", "assigned_to", "resolution_notes",
        ]
        widgets = {
            **_widgets("contact", "category", "priority", "status", "assigned_to", kind="select"),
            **_widgets("customer_name", "phone", "subject"),
            **_widgets("description", "resolution_notes", kind="textarea"),
        }


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["contact", "customer_name", "category", "rating", "comments"]
        widgets = {
            **_widgets("contact", "category", "rating", kind="select"),
            **_widgets("customer_name"),
            **_widgets("comments", kind="textarea"),
        }


class FollowUpForm(forms.ModelForm):
    class Meta:
        model = FollowUp
        fields = [
            "contact", "customer_name", "related_complaint", "follow_up_type",
            "scheduled_date", "assigned_to", "notes",
        ]
        widgets = {
            **_widgets("contact", "related_complaint", "follow_up_type", "assigned_to", kind="select"),
            **_widgets("customer_name"),
            **_widgets("scheduled_date", kind="date"),
            **_widgets("notes", kind="textarea"),
        }


class PromotionForm(forms.ModelForm):
    class Meta:
        model = Promotion
        fields = [
            "title", "description", "discount_type", "discount_value",
            "start_date", "end_date", "active", "channel", "message",
        ]
        widgets = {
            **_widgets("title"),
            **_widgets("discount_type", "channel", kind="select"),
            **_widgets("discount_value", kind="number"),
            **_widgets("start_date", "end_date", kind="date"),
            **_widgets("active", kind="checkbox"),
            **_widgets("description", "message", kind="textarea"),
        }


class SmsComposeForm(forms.Form):
    contact = forms.ModelChoiceField(
        queryset=Contact.objects.exclude(phone__isnull=True).exclude(phone=""),
        required=False, widget=forms.Select(attrs={"class": TEXT_INPUT}),
        help_text="Pick a contact to auto-fill the number, or type one below.",
    )
    recipient = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": TEXT_INPUT, "placeholder": "e.g. 254712345678"}),
    )
    message = forms.CharField(widget=forms.Textarea(attrs={"class": TEXT_INPUT, "rows": 4}))

    def clean(self):
        cleaned = super().clean()
        contact = cleaned.get("contact")
        recipient = (cleaned.get("recipient") or "").strip()
        if not recipient and contact and contact.phone:
            recipient = contact.phone.strip()
        if not recipient:
            raise forms.ValidationError("Choose a contact with a phone number, or type a recipient number.")
        cleaned["recipient"] = recipient
        return cleaned


class EmailComposeForm(forms.Form):
    contact = forms.ModelChoiceField(
        queryset=Contact.objects.exclude(email__isnull=True).exclude(email=""),
        required=False, widget=forms.Select(attrs={"class": TEXT_INPUT}),
        help_text="Pick a contact to auto-fill the address, or type one below.",
    )
    recipient = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": TEXT_INPUT}))
    subject = forms.CharField(widget=forms.TextInput(attrs={"class": TEXT_INPUT}))
    body = forms.CharField(widget=forms.Textarea(attrs={"class": TEXT_INPUT, "rows": 6}))

    def clean(self):
        cleaned = super().clean()
        contact = cleaned.get("contact")
        recipient = (cleaned.get("recipient") or "").strip()
        if not recipient and contact and contact.email:
            recipient = contact.email.strip()
        if not recipient:
            raise forms.ValidationError("Choose a contact with an email address, or type a recipient address.")
        cleaned["recipient"] = recipient
        return cleaned


class LoyaltyCreateForm(forms.Form):
    contact = forms.ModelChoiceField(
        queryset=Contact.objects.filter(loyalty__isnull=True),
        widget=forms.Select(attrs={"class": TEXT_INPUT}),
        label="Customer",
    )


class LoyaltyProgramForm(forms.ModelForm):
    class Meta:
        model = LoyaltyProgram
        fields = ["points_per_amount", "redemption_value"]
        widgets = _widgets("points_per_amount", "redemption_value", kind="number")


class LoyaltyAdjustForm(forms.Form):
    points = forms.FloatField(widget=forms.NumberInput(attrs={"class": TEXT_INPUT, "step": "0.01"}))
    transaction_type = forms.ChoiceField(
        choices=[(LoyaltyTransaction.EARN, "Earn (add)"), (LoyaltyTransaction.REDEEM, "Redeem (subtract)"), (LoyaltyTransaction.ADJUSTMENT, "Adjustment")],
        widget=forms.Select(attrs={"class": TEXT_INPUT}),
    )
    note = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": TEXT_INPUT}))

    def clean(self):
        cleaned = super().clean()
        points = cleaned.get("points")
        tx_type = cleaned.get("transaction_type")
        if points is not None and tx_type == LoyaltyTransaction.REDEEM and points > 0:
            cleaned["points"] = -points
        return cleaned
