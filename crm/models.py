from django.conf import settings
from django.db import models

from contacts.models import Contact


class Complaint(models.Model):
    LOW, MEDIUM, HIGH, URGENT = "low", "medium", "high", "urgent"
    PRIORITY_CHOICES = [(LOW, "Low"), (MEDIUM, "Medium"), (HIGH, "High"), (URGENT, "Urgent")]

    OPEN, IN_PROGRESS, RESOLVED, CLOSED = "open", "in_progress", "resolved", "closed"
    STATUS_CHOICES = [(OPEN, "Open"), (IN_PROGRESS, "In Progress"), (RESOLVED, "Resolved"), (CLOSED, "Closed")]

    CATEGORY_CHOICES = [
        (c, c) for c in ["Product Quality", "Delivery", "Billing", "Service", "Other"]
    ]

    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="complaints")
    customer_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=50, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="Other")
    subject = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)
    assigned_to = models.ForeignKey(
        "employees.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_complaints"
    )
    resolution_notes = models.TextField(blank=True)
    date_raised = models.DateTimeField(auto_now_add=True)
    date_resolved = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-date_raised"]

    def __str__(self):
        return f"{self.customer_name} — {self.subject}"


class Feedback(models.Model):
    CATEGORY_CHOICES = [
        (c, c) for c in ["Service", "Product", "Pricing", "Delivery", "Other"]
    ]
    RATING_CHOICES = [(i, f"{i} star{'s' if i != 1 else ''}") for i in range(1, 6)]

    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="feedback_entries")
    customer_name = models.CharField(max_length=150)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="Service")
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comments = models.TextField(blank=True)
    date_submitted = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_submitted"]

    def __str__(self):
        return f"{self.customer_name} — {self.rating}★"


class FollowUp(models.Model):
    CALL, VISIT, SMS, EMAIL, OTHER = "call", "visit", "sms", "email", "other"
    TYPE_CHOICES = [(CALL, "Phone Call"), (VISIT, "Visit"), (SMS, "SMS"), (EMAIL, "Email"), (OTHER, "Other")]

    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="follow_ups")
    customer_name = models.CharField(max_length=150)
    related_complaint = models.ForeignKey(
        Complaint, null=True, blank=True, on_delete=models.SET_NULL, related_name="follow_ups"
    )
    follow_up_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=CALL)
    scheduled_date = models.DateField()
    completed = models.BooleanField(default=False)
    completed_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        "employees.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_follow_ups"
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_date"]

    def __str__(self):
        return f"{self.customer_name} — {self.get_follow_up_type_display()} ({self.scheduled_date})"


class Promotion(models.Model):
    PERCENTAGE, FIXED = "percentage", "fixed"
    DISCOUNT_TYPE_CHOICES = [(PERCENTAGE, "Percentage"), (FIXED, "Fixed Amount")]

    SMS_CHANNEL, EMAIL_CHANNEL, BOTH_CHANNELS = "sms", "email", "both"
    CHANNEL_CHOICES = [(SMS_CHANNEL, "SMS"), (EMAIL_CHANNEL, "Email"), (BOTH_CHANNELS, "SMS + Email")]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default=PERCENTAGE)
    discount_value = models.FloatField(default=0)
    start_date = models.DateField()
    end_date = models.DateField()
    active = models.BooleanField(default=True)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default=SMS_CHANNEL)
    message = models.TextField(help_text="The SMS/email body sent to customers when this promotion goes out.")
    sent_at = models.DateTimeField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.title

    @property
    def is_current(self):
        from datetime import date
        return self.active and self.start_date <= date.today() <= self.end_date


class SmsMessage(models.Model):
    PENDING, SENT, FAILED = "pending", "sent", "failed"
    STATUS_CHOICES = [(PENDING, "Pending"), (SENT, "Sent"), (FAILED, "Failed")]

    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="sms_messages")
    promotion = models.ForeignKey(Promotion, null=True, blank=True, on_delete=models.SET_NULL, related_name="sms_messages")
    recipient = models.CharField(max_length=50)
    sender_id = models.CharField(max_length=50, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    provider_response = models.TextField(blank=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"SMS to {self.recipient} ({self.status})"


class EmailLog(models.Model):
    PENDING, SENT, FAILED = "pending", "sent", "failed"
    STATUS_CHOICES = [(PENDING, "Pending"), (SENT, "Sent"), (FAILED, "Failed")]

    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="email_logs")
    promotion = models.ForeignKey(Promotion, null=True, blank=True, on_delete=models.SET_NULL, related_name="email_logs")
    recipient = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    error_message = models.TextField(blank=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"Email to {self.recipient} ({self.status})"


class LoyaltyProgram(models.Model):
    """Singleton config row (see get_solo()) for the points-based loyalty scheme."""

    points_per_amount = models.FloatField(
        default=100, help_text="Customer earns 1 point for every this many KES spent on a paid sale."
    )
    redemption_value = models.FloatField(
        default=1, help_text="KES value of 1 redeemed point (used only for display/reference)."
    )

    def __str__(self):
        return "Loyalty Program Settings"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CustomerLoyalty(models.Model):
    contact = models.OneToOneField(Contact, on_delete=models.CASCADE, related_name="loyalty")
    points_balance = models.FloatField(default=0)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-points_balance"]
        verbose_name_plural = "Customer loyalty accounts"

    def __str__(self):
        return f"{self.contact.name} — {self.points_balance:g} pts"


class LoyaltyTransaction(models.Model):
    EARN, REDEEM, ADJUSTMENT = "earn", "redeem", "adjustment"
    TYPE_CHOICES = [(EARN, "Earned"), (REDEEM, "Redeemed"), (ADJUSTMENT, "Adjustment")]

    customer_loyalty = models.ForeignKey(CustomerLoyalty, on_delete=models.CASCADE, related_name="transactions")
    points = models.FloatField(help_text="Positive for earn/adjustment-up, negative for redeem/adjustment-down.")
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=EARN)
    reference = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"{self.customer_loyalty.contact.name} {self.points:+g} ({self.transaction_type})"
