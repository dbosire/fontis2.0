from django.conf import settings
from django.db import models


class DebtPayment(models.Model):
    """A payment recorded against an UNPAID/PARTIAL Sale — mirrors
    finance.models.BillPayment. See debts/services.py::record_debt_payment for the
    logic that creates these and settles the Sale once the balance reaches zero."""

    CASH, MPESA = "cash", "mpesa"
    METHOD_CHOICES = [(CASH, "Cash"), (MPESA, "M-Pesa")]

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
