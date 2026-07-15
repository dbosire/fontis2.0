import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models


# USE_TZ=False project-wide (see fontis/settings/base.py) — naive local time only.
def _now():
    return datetime.now(ZoneInfo("Africa/Nairobi")).replace(tzinfo=None)


class MpesaTransaction(models.Model):
    TransactionType = models.CharField(max_length=255, null=True, blank=True)
    TransID = models.CharField(max_length=255, unique=True, null=True, blank=True)
    TransTime = models.CharField(max_length=255, null=True, blank=True)  # raw 'YmdHis' string from Safaricom
    TransAmount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    BusinessShortCode = models.CharField(max_length=255, null=True, blank=True)
    BillRefNumber = models.CharField(max_length=255, null=True, blank=True)
    InvoiceNumber = models.CharField(max_length=255, null=True, blank=True)
    OrgAccountBalance = models.CharField(max_length=255, null=True, blank=True)
    ThirdPartyTransID = models.CharField(max_length=255, null=True, blank=True)
    MSISDN = models.CharField(max_length=255, null=True, blank=True)
    FirstName = models.CharField(max_length=255, null=True, blank=True)
    MiddleName = models.CharField(max_length=255, null=True, blank=True)
    LastName = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "mpesa_transactions"
        managed = False
        ordering = ["-id"]

    def __str__(self):
        return self.TransID or f"mpesa#{self.pk}"

    @property
    def trans_datetime(self):
        if not self.TransTime:
            return None
        try:
            return datetime.strptime(self.TransTime, "%Y%m%d%H%M%S")
        except ValueError:
            return None

    @property
    def full_name(self):
        return " ".join(filter(None, [self.FirstName, self.MiddleName, self.LastName]))


def _default_expiry():
    return _now() + timedelta(hours=48)


class PaymentLink(models.Model):
    """A shareable, unauthenticated payment page covering one or more of a single
    customer's unpaid Sales. `amount` is a snapshot taken at creation time and never
    recomputed live, so the payer always sees a stable figure even if a linked Sale is
    edited afterward — see finance module design notes for the same philosophy applied
    to journal entries."""

    PENDING, PAID, EXPIRED, CANCELLED = "pending", "paid", "expired", "cancelled"
    STATUS_CHOICES = [(PENDING, "Pending"), (PAID, "Paid"), (EXPIRED, "Expired"), (CANCELLED, "Cancelled")]

    STK, DIRECT, MANUAL = "stk", "direct", "manual"
    CONFIRMED_VIA_CHOICES = [(STK, "STK Push"), (DIRECT, "Direct Payment"), (MANUAL, "Manual (staff)")]

    token = models.CharField(max_length=64, unique=True, editable=False)
    sales = models.ManyToManyField("sales.Sale", related_name="payment_links")
    customer_name = models.CharField(max_length=150)
    phone_number = models.CharField(
        max_length=20, blank=True,
        help_text="Prefills the STK Push field. Also required for Direct Payment to auto-reconcile.",
    )
    amount = models.FloatField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_expiry)
    paid_at = models.DateTimeField(null=True, blank=True)
    confirmed_via = models.CharField(max_length=10, choices=CONFIRMED_VIA_CHOICES, blank=True)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"Payment link for {self.customer_name} (KES {self.amount:g})"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return _now() > self.expires_at

    @classmethod
    def create_for_sales(cls, sales, *, phone_number="", user=None):
        """sales: an iterable/queryset of currently-outstanding (UNPAID or PARTIAL)
        Sale rows belonging to one customer. Raises ValueError if that's not the
        case — callers should validate their selection before calling this, this is
        the last-line guard. `amount` is the sum of each sale's *remaining balance*,
        not its original amount, so a link generated for a partially-paid debt only
        charges what's actually still owed."""
        sales = list(sales)
        if not sales:
            raise ValueError("Select at least one debt.")
        customer_names = {s.customer_name for s in sales}
        if len(customer_names) > 1:
            raise ValueError("All selected debts must belong to the same customer.")
        from sales.models import Sale
        if any(s.status not in (Sale.UNPAID, Sale.PARTIAL) for s in sales):
            raise ValueError("All selected debts must currently be outstanding.")

        link = cls.objects.create(
            customer_name=sales[0].customer_name,
            phone_number=phone_number,
            amount=round(sum(s.balance_due for s in sales), 2),
            created_by=user if user and getattr(user, "is_authenticated", False) else None,
        )
        link.sales.set(sales)
        return link


class STKPushAttempt(models.Model):
    REQUESTED, SUCCESS, FAILED, CANCELLED, TIMEOUT = "requested", "success", "failed", "cancelled", "timeout"
    STATUS_CHOICES = [
        (REQUESTED, "Requested"), (SUCCESS, "Success"), (FAILED, "Failed"),
        (CANCELLED, "Cancelled"), (TIMEOUT, "Timeout"),
    ]

    payment_link = models.ForeignKey(PaymentLink, on_delete=models.CASCADE, related_name="stk_attempts")
    phone_number = models.CharField(max_length=20)
    amount = models.FloatField()
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=REQUESTED)
    result_code = models.CharField(max_length=10, blank=True)
    result_desc = models.CharField(max_length=255, blank=True)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"STK push {self.phone_number} KES {self.amount:g} ({self.status})"


class MpesaC2BTransaction(models.Model):
    """Raw log of every C2B Confirmation webhook call — the 'Direct payment' path,
    where a customer pays the Till manually from their own phone with no way for us
    to trigger or track the attempt in advance. trans_id is Safaricom's own ID and the
    idempotency key: webhooks can be retried, this table must never double-process one."""

    UNMATCHED, MATCHED, DUPLICATE, IGNORED = "unmatched", "matched", "duplicate", "ignored"
    STATUS_CHOICES = [
        (UNMATCHED, "Unmatched"), (MATCHED, "Matched"),
        (DUPLICATE, "Duplicate (already paid via another channel)"), (IGNORED, "Ignored"),
    ]

    trans_id = models.CharField(max_length=100, unique=True)
    trans_time = models.CharField(max_length=20, blank=True)  # raw Safaricom 'YmdHis' string
    trans_amount = models.FloatField()
    business_short_code = models.CharField(max_length=20, blank=True)
    bill_ref_number = models.CharField(max_length=100, blank=True)
    msisdn = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    raw_payload = models.TextField(blank=True)
    matched_payment_link = models.ForeignKey(
        PaymentLink, null=True, blank=True, on_delete=models.SET_NULL, related_name="c2b_transactions"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=UNMATCHED)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"C2B {self.trans_id} KES {self.trans_amount:g} ({self.status})"


class LegacyTransactionAllocation(models.Model):
    """Records which of a legacy `MpesaTransaction`'s amount was applied to which
    Sale(s). That table is managed=False (predates this app, no allocation columns of
    its own) and predates this app's AutoField-PK-fix convention, so this keys off
    TransID — its natural unique key — rather than an FK to it."""

    trans_id = models.CharField(max_length=255, db_index=True)
    sale = models.ForeignKey("sales.Sale", on_delete=models.CASCADE, related_name="legacy_mpesa_allocations")
    amount = models.FloatField()
    allocated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"{self.trans_id} -> Sale #{self.sale_id} (KES {self.amount:g})"
