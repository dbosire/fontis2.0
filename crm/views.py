from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from contacts.models import Contact
from core.mixins import ModulePermissionRequiredMixin

from .forms import (
    ComplaintForm, EmailComposeForm, FeedbackForm, FollowUpForm, LoyaltyCreateForm,
    LoyaltyAdjustForm, LoyaltyProgramForm, PromotionForm, SmsComposeForm,
)
from .models import (
    Complaint, CustomerLoyalty, EmailLog, Feedback, FollowUp, LoyaltyProgram,
    LoyaltyTransaction, Promotion, SmsMessage,
)
from .services.email import send_customer_email
from .services.loyalty import adjust_points
from .services.sms import send_sms


class ViewCrmMixin(ModulePermissionRequiredMixin):
    module_name = "crm"
    permission_level = "view"


class EditCrmMixin(ModulePermissionRequiredMixin):
    module_name = "crm"
    permission_level = "edit"


# See reports/views.py for why this can't just be timezone.localdate() (USE_TZ=False).
def _now():
    return datetime.now(ZoneInfo("Africa/Nairobi")).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Complaints
# ---------------------------------------------------------------------------

class ComplaintListView(ViewCrmMixin, ListView):
    model = Complaint
    template_name = "crm/complaint_list.html"
    context_object_name = "complaints"
    paginate_by = 30

    def get_queryset(self):
        qs = Complaint.objects.select_related("contact", "assigned_to")
        status = self.request.GET.get("status", "")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = Complaint.STATUS_CHOICES
        ctx["selected_status"] = self.request.GET.get("status", "")
        return ctx


class ComplaintCreateView(EditCrmMixin, CreateView):
    model = Complaint
    form_class = ComplaintForm
    template_name = "crm/complaint_form.html"
    success_url = reverse_lazy("crm:complaints")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Complaint logged.")
        return super().form_valid(form)


class ComplaintUpdateView(EditCrmMixin, UpdateView):
    model = Complaint
    form_class = ComplaintForm
    template_name = "crm/complaint_form.html"
    success_url = reverse_lazy("crm:complaints")

    def form_valid(self, form):
        if form.instance.status in (Complaint.RESOLVED, Complaint.CLOSED) and not form.instance.date_resolved:
            form.instance.date_resolved = _now()
        messages.success(self.request, "Complaint updated.")
        return super().form_valid(form)


class ComplaintDeleteView(EditCrmMixin, DeleteView):
    model = Complaint
    success_url = reverse_lazy("crm:complaints")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("crm:complaints")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Complaint deleted.")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class FeedbackListView(ViewCrmMixin, ListView):
    model = Feedback
    template_name = "crm/feedback_list.html"
    context_object_name = "feedback_entries"
    paginate_by = 30

    def get_queryset(self):
        return Feedback.objects.select_related("contact")


class FeedbackCreateView(EditCrmMixin, CreateView):
    model = Feedback
    form_class = FeedbackForm
    template_name = "crm/feedback_form.html"
    success_url = reverse_lazy("crm:feedback")

    def form_valid(self, form):
        messages.success(self.request, "Feedback recorded.")
        return super().form_valid(form)


class FeedbackUpdateView(EditCrmMixin, UpdateView):
    model = Feedback
    form_class = FeedbackForm
    template_name = "crm/feedback_form.html"
    success_url = reverse_lazy("crm:feedback")

    def form_valid(self, form):
        messages.success(self.request, "Feedback updated.")
        return super().form_valid(form)


class FeedbackDeleteView(EditCrmMixin, DeleteView):
    model = Feedback
    success_url = reverse_lazy("crm:feedback")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("crm:feedback")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Feedback deleted.")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

class FollowUpListView(ViewCrmMixin, ListView):
    model = FollowUp
    template_name = "crm/followup_list.html"
    context_object_name = "follow_ups"
    paginate_by = 30

    def get_queryset(self):
        qs = FollowUp.objects.select_related("contact", "assigned_to", "related_complaint")
        show = self.request.GET.get("show", "pending")
        if show == "pending":
            qs = qs.filter(completed=False)
        elif show == "completed":
            qs = qs.filter(completed=True)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["selected_show"] = self.request.GET.get("show", "pending")
        return ctx


class FollowUpCreateView(EditCrmMixin, CreateView):
    model = FollowUp
    form_class = FollowUpForm
    template_name = "crm/followup_form.html"
    success_url = reverse_lazy("crm:followups")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Follow-up scheduled.")
        return super().form_valid(form)


class FollowUpUpdateView(EditCrmMixin, UpdateView):
    model = FollowUp
    form_class = FollowUpForm
    template_name = "crm/followup_form.html"
    success_url = reverse_lazy("crm:followups")

    def form_valid(self, form):
        messages.success(self.request, "Follow-up updated.")
        return super().form_valid(form)


class FollowUpDeleteView(EditCrmMixin, DeleteView):
    model = FollowUp
    success_url = reverse_lazy("crm:followups")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("crm:followups")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Follow-up deleted.")
        return super().form_valid(form)


class FollowUpCompleteView(EditCrmMixin, View):
    def post(self, request, pk):
        follow_up = get_object_or_404(FollowUp, pk=pk)
        follow_up.completed = True
        follow_up.completed_date = _now()
        follow_up.save(update_fields=["completed", "completed_date"])
        messages.success(request, "Follow-up marked complete.")
        return redirect(reverse("crm:followups"))


# ---------------------------------------------------------------------------
# SMS
# ---------------------------------------------------------------------------

class SmsLogListView(ViewCrmMixin, ListView):
    model = SmsMessage
    template_name = "crm/sms_list.html"
    context_object_name = "messages_"
    paginate_by = 50

    def get_queryset(self):
        return SmsMessage.objects.select_related("contact", "sent_by")


class SmsSendView(EditCrmMixin, View):
    template_name = "crm/sms_send.html"

    def get(self, request):
        return render(request, self.template_name, {"form": SmsComposeForm()})

    def post(self, request):
        form = SmsComposeForm(request.POST)
        if form.is_valid():
            log = send_sms(
                form.cleaned_data["recipient"],
                form.cleaned_data["message"],
                contact=form.cleaned_data.get("contact"),
                user=request.user,
            )
            if log.status == SmsMessage.SENT:
                messages.success(request, f"SMS sent to {log.recipient}.")
            else:
                messages.error(request, f"SMS to {log.recipient} failed — see the log for details.")
            return redirect(reverse("crm:sms_log"))
        return render(request, self.template_name, {"form": form})


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

class EmailLogListView(ViewCrmMixin, ListView):
    model = EmailLog
    template_name = "crm/email_list.html"
    context_object_name = "messages_"
    paginate_by = 50

    def get_queryset(self):
        return EmailLog.objects.select_related("contact", "sent_by")


class EmailSendView(EditCrmMixin, View):
    template_name = "crm/email_send.html"

    def get(self, request):
        return render(request, self.template_name, {"form": EmailComposeForm()})

    def post(self, request):
        form = EmailComposeForm(request.POST)
        if form.is_valid():
            log = send_customer_email(
                form.cleaned_data["recipient"],
                form.cleaned_data["subject"],
                form.cleaned_data["body"],
                contact=form.cleaned_data.get("contact"),
                user=request.user,
            )
            if log.status == EmailLog.SENT:
                messages.success(request, f"Email sent to {log.recipient}.")
            else:
                messages.error(request, f"Email to {log.recipient} failed — see the log for details.")
            return redirect(reverse("crm:email_log"))
        return render(request, self.template_name, {"form": form})


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------

class PromotionListView(ViewCrmMixin, ListView):
    model = Promotion
    template_name = "crm/promotion_list.html"
    context_object_name = "promotions"


class PromotionCreateView(EditCrmMixin, CreateView):
    model = Promotion
    form_class = PromotionForm
    template_name = "crm/promotion_form.html"
    success_url = reverse_lazy("crm:promotions")

    def form_valid(self, form):
        messages.success(self.request, "Promotion saved.")
        return super().form_valid(form)


class PromotionUpdateView(EditCrmMixin, UpdateView):
    model = Promotion
    form_class = PromotionForm
    template_name = "crm/promotion_form.html"
    success_url = reverse_lazy("crm:promotions")

    def form_valid(self, form):
        messages.success(self.request, "Promotion updated.")
        return super().form_valid(form)


class PromotionDeleteView(EditCrmMixin, DeleteView):
    model = Promotion
    success_url = reverse_lazy("crm:promotions")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("crm:promotions")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Promotion deleted.")
        return super().form_valid(form)


class PromotionSendView(EditCrmMixin, View):
    """Bulk-sends a promotion's message to every contact that has the channel's
    required detail (phone for SMS, email for Email). Each send is logged individually
    via the same send_sms/send_customer_email path used for one-off messages."""

    def post(self, request, pk):
        promotion = get_object_or_404(Promotion, pk=pk)
        sent_sms = sent_email = 0

        if promotion.channel in (Promotion.SMS_CHANNEL, Promotion.BOTH_CHANNELS):
            for contact in Contact.objects.exclude(phone__isnull=True).exclude(phone=""):
                log = send_sms(contact.phone, promotion.message, contact=contact, promotion=promotion, user=request.user)
                if log.status == SmsMessage.SENT:
                    sent_sms += 1

        if promotion.channel in (Promotion.EMAIL_CHANNEL, Promotion.BOTH_CHANNELS):
            for contact in Contact.objects.exclude(email__isnull=True).exclude(email=""):
                log = send_customer_email(
                    contact.email, promotion.title, promotion.message, contact=contact, promotion=promotion, user=request.user
                )
                if log.status == EmailLog.SENT:
                    sent_email += 1

        promotion.sent_at = _now()
        promotion.save(update_fields=["sent_at"])
        messages.success(request, f"Promotion sent — {sent_sms} SMS, {sent_email} email(s) delivered.")
        return redirect(reverse("crm:promotions"))


# ---------------------------------------------------------------------------
# Customer loyalty
# ---------------------------------------------------------------------------

class LoyaltyListView(ViewCrmMixin, ListView):
    model = CustomerLoyalty
    template_name = "crm/loyalty_list.html"
    context_object_name = "loyalty_accounts"

    def get_queryset(self):
        return CustomerLoyalty.objects.select_related("contact")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["program"] = LoyaltyProgram.get_solo()
        ctx["create_form"] = LoyaltyCreateForm()
        return ctx


class LoyaltyCreateView(EditCrmMixin, View):
    def post(self, request):
        form = LoyaltyCreateForm(request.POST)
        if form.is_valid():
            loyalty = CustomerLoyalty.objects.create(contact=form.cleaned_data["contact"])
            messages.success(request, f"Loyalty account created for {loyalty.contact.name}.")
            return redirect(reverse("crm:loyalty_adjust", args=[loyalty.pk]))
        messages.error(request, "Choose a customer to create a loyalty account for.")
        return redirect(reverse("crm:loyalty"))


class LoyaltyAdjustView(EditCrmMixin, View):
    template_name = "crm/loyalty_adjust.html"

    def get_object(self):
        return get_object_or_404(CustomerLoyalty, pk=self.kwargs["pk"])

    def get(self, request, pk):
        loyalty = self.get_object()
        ctx = {"form": LoyaltyAdjustForm(), "loyalty": loyalty, "transactions": loyalty.transactions.all()[:20]}
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        loyalty = self.get_object()
        form = LoyaltyAdjustForm(request.POST)
        if form.is_valid():
            adjust_points(
                loyalty, form.cleaned_data["points"], form.cleaned_data["transaction_type"],
                note=form.cleaned_data.get("note", ""), user=request.user,
            )
            messages.success(request, "Loyalty balance updated.")
            return redirect(reverse("crm:loyalty_adjust", args=[loyalty.pk]))
        ctx = {"form": form, "loyalty": loyalty, "transactions": loyalty.transactions.all()[:20]}
        return render(request, self.template_name, ctx)


class LoyaltySettingsView(EditCrmMixin, View):
    template_name = "crm/loyalty_settings.html"

    def get(self, request):
        program = LoyaltyProgram.get_solo()
        return render(request, self.template_name, {"form": LoyaltyProgramForm(instance=program)})

    def post(self, request):
        program = LoyaltyProgram.get_solo()
        form = LoyaltyProgramForm(request.POST, instance=program)
        if form.is_valid():
            form.save()
            messages.success(request, "Loyalty program settings updated.")
            return redirect(reverse("crm:loyalty"))
        return render(request, self.template_name, {"form": form})
