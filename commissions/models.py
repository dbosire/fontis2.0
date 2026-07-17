from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from django.db import models
from django.db.models import Sum

from sales.models import Sale


def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


class CommissionAccount(models.Model):
    """Links a customer to the Employee who earns commission on that customer's sales
    for a fixed window after onboarding. No uniqueness constraint on `customer` — a
    customer can be reassigned or re-onboarded to a new account over time."""

    customer = models.ForeignKey("contacts.Contact", on_delete=models.PROTECT, related_name="commission_accounts")
    account_manager = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="commission_accounts")
    commission_rate = models.FloatField(default=0.15, help_text="Enter as a fraction — e.g. 0.15 for 15%.")
    onboarding_date = models.DateField(default=_today, help_text="Commission accrues on this customer's paid sales for 3 months from this date.")
    notes = models.TextField(blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"{self.customer.name} -> {self.account_manager.get_full_name()} ({self.commission_rate:.0%})"

    @property
    def commission_window_end(self):
        return self.onboarding_date + relativedelta(months=3)

    @property
    def is_window_active(self):
        return _today() <= self.commission_window_end

    def matching_sales(self, period_start=None, period_end=None):
        """Paid sales for this account's customer, restricted to the commission
        window and optionally further restricted to a payroll period."""
        start = max(self.onboarding_date, period_start) if period_start else self.onboarding_date
        end = min(self.commission_window_end, period_end) if period_end else self.commission_window_end
        if start > end:
            return Sale.objects.none()
        return Sale.objects.filter(
            customer_name__iexact=self.customer.name.strip(),
            status__in=[Sale.CASH, Sale.MPESA, Sale.CREDIT],
            date_created__date__gte=start,
            date_created__date__lte=end,
        )

    def earned_commission(self, period_start=None, period_end=None):
        total = self.matching_sales(period_start, period_end).aggregate(total=Sum("amount"))["total"] or 0
        return round(total * self.commission_rate, 2)
