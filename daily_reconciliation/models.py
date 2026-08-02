from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models


def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


class DailyReconciliation(models.Model):
    """One cash-up per day. Only `cash_collected` is real input — expected/actual
    cash and M-Pesa totals (and both variances) are computed live against
    Sale/DebtPayment/MpesaTransaction for `date` (see services.py), never frozen, so
    a later correction to a sale is reflected automatically rather than going stale."""

    date = models.DateField(unique=True, default=_today)
    cash_collected = models.FloatField(help_text="Physical cash counted at close of day.")
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Reconciliation {self.date}"


class CashDepositAllocation(models.Model):
    """Links the M-Pesa transaction that received a day's physical cash takings — an
    agent depositing the day's till count into M-Pesa after close — to the
    DailyReconciliation it settles. Keyed off TransID rather than an FK: like
    mpesa.LegacyTransactionAllocation, mpesa_transactions is a managed=False legacy
    table with no allocation columns of its own. `trans_id` is unique here since one
    M-Pesa transaction is one day's deposit, never split across days. Manual,
    staff-driven — staff confirm a candidate transaction surfaced by services.py's
    amount+date matching, never an automatic/silent match."""

    reconciliation = models.OneToOneField(DailyReconciliation, on_delete=models.CASCADE, related_name="deposit")
    trans_id = models.CharField(max_length=255, unique=True)
    amount = models.FloatField()
    allocated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.trans_id} -> {self.reconciliation.date} (KES {self.amount:g})"
