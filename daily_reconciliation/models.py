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
    """Links an M-Pesa transaction — or a slice of one — to the DailyReconciliation
    it (partly) settles. Both sides are plain FKs, not one-to-one/unique: a day's
    cash is often banked in more than one tranche (several transactions for one
    day), and a single large transaction can just as easily cover more than one
    day's takings in one lump sum (one transaction split across several days) — see
    services.py's deposit_available_amount(), which tracks how much of a given
    `trans_id` remains unclaimed across every row here (plus mpesa's own
    LegacyTransactionAllocation for customer debts) so the same money can never be
    claimed twice. Keyed off TransID rather than an FK to the transaction itself:
    like mpesa.LegacyTransactionAllocation, mpesa_transactions is a managed=False
    legacy table with no allocation columns of its own. `amount` is however much of
    the transaction was allocated to *this* day, not necessarily its full value.
    Manual, staff-driven — staff confirm a candidate transaction surfaced by
    services.py's amount+date matching, never an automatic/silent match.

    `depositor_name` is who physically banked the cash — not necessarily
    `allocated_by`, which is whoever in the office confirmed the match afterward and
    may be a different person entirely (e.g. an accountant reconciling days later).
    Defaults to the M-Pesa transaction's own registered name in the UI but is a plain
    editable field, since that name may just be a shared agent line rather than the
    actual staff member who made the deposit."""

    reconciliation = models.ForeignKey(DailyReconciliation, on_delete=models.CASCADE, related_name="deposits")
    trans_id = models.CharField(max_length=255, db_index=True)
    amount = models.FloatField()
    depositor_name = models.CharField(max_length=150)
    allocated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_created"]

    def __str__(self):
        return f"{self.trans_id} -> {self.reconciliation.date} (KES {self.amount:g})"
