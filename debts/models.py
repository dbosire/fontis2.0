from django.conf import settings
from django.db import models


class DebtPayment(models.Model):
    """A payment recorded against an UNPAID/PARTIAL Sale — mirrors
    finance.models.BillPayment. See debts/services.py::record_debt_payment for the
    logic that creates these and settles the Sale once the balance reaches zero."""

    CASH, MPESA, CREDIT = "cash", "mpesa", "credit"
    METHOD_CHOICES = [(CASH, "Cash"), (MPESA, "M-Pesa"), (CREDIT, "Credit")]

    sale = models.ForeignKey("sales.Sale", on_delete=models.CASCADE, related_name="debt_payments")
    amount = models.FloatField()
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=10, choices=METHOD_CHOICES, default=CASH)
    notes = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]

    def __str__(self):
        return f"Payment {self.amount:g} on {self.sale}"


class CustomerCredit(models.Model):
    """A running ledger of a customer's credit balance — positive amount = credit
    added (an overpayment on a debt, or a prepayment with no debt yet), negative =
    credit consumed (auto-applied or manually applied to a debt). The balance is just
    the sum of a customer_name's entries; see debts/services.py::customer_credit_balance.

    Keyed on customer_name (matching the case-insensitive string convention used
    throughout this app — Sale has no FK to a customer entity), not a Contact FK."""

    OVERPAYMENT, PREPAYMENT, APPLIED = "overpayment", "prepayment", "applied"
    SOURCE_CHOICES = [
        (OVERPAYMENT, "Overpayment"), (PREPAYMENT, "Prepayment"), (APPLIED, "Applied to debt"),
    ]

    customer_name = models.CharField(max_length=255)
    amount = models.FloatField(help_text="Positive = credit added, negative = credit consumed.")
    payment_date = models.DateField()
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    payment_method = models.CharField(
        max_length=10, choices=[(DebtPayment.CASH, "Cash"), (DebtPayment.MPESA, "M-Pesa")], blank=True,
        help_text="How the underlying cash was received — only set for Overpayment/Prepayment entries.",
    )
    related_sale = models.ForeignKey(
        "sales.Sale", null=True, blank=True, on_delete=models.SET_NULL, related_name="credit_entries"
    )
    notes = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]

    def __str__(self):
        return f"{self.customer_name}: {self.amount:+g} ({self.get_source_display()})"
