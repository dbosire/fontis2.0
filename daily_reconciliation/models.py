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
