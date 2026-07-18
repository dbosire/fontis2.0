from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.views.generic import TemplateView

from core.mixins import ModulePermissionRequiredMixin
from debts.models import DebtPayment
from expenses.models import Expense
from finance.models import JournalEntry, JournalLine
from inventory.models import RawMaterial, StockMovement
from sales.models import Sale, SaleItem


class ViewReportsMixin(ModulePermissionRequiredMixin):
    module_name = "reports"
    permission_level = "view"


# USE_TZ=False (see settings) because the existing data is naive local time, so
# Django won't reliably derive "today" from TIME_ZONE on its own (time.tzset()
# isn't available on Windows). Compute it explicitly against Africa/Nairobi to
# match the PHP app's explicit date_default_timezone_set('Africa/Nairobi').
def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


def _months_before(d, n):
    """First day of the month that is n months before d's month."""
    year, month = d.year, d.month - n
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _status_bucket(qs, status):
    agg = qs.filter(status=status).aggregate(total=Sum("amount"), count=Count("id"))
    return {"total": agg["total"] or 0, "count": agg["count"] or 0}


def _debt_total(qs):
    """Like _status_bucket, but for "outstanding debt" — UNPAID and PARTIAL sales
    together, summed by balance_due (not amount, since a PARTIAL sale's amount
    overstates what's actually still owed). Can't be a DB .aggregate(Sum(...)) since
    balance_due depends on each Sale's related debt_payments."""
    sales = qs.filter(status__in=[Sale.UNPAID, Sale.PARTIAL])
    return {"total": sum(s.balance_due for s in sales), "count": sales.count()}


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = _today()
        month_start = today.replace(day=1)
        week_start = today - timedelta(days=6)

        month_sales = Sale.objects.filter(date_created__date__gte=month_start)
        ctx["month_sales_total"] = month_sales.aggregate(total=Sum("amount"))["total"] or 0
        ctx["month_sales_count"] = month_sales.count()
        ctx["month_expenses_total"] = (
            Expense.objects.filter(date_created__date__gte=month_start).aggregate(total=Sum("amount"))["total"] or 0
        )

        # Total water sold this month, in litres, based on each product's configured volume
        month_items = SaleItem.objects.filter(sale__date_created__date__gte=month_start).select_related("jar_type")
        ctx["month_water_liters"] = sum(item.quantity * item.jar_type.volume_in_liters for item in month_items)

        # 1. This month's debts vs total (all-time) debts — includes PARTIAL sales,
        # summed by remaining balance, not their original full amount.
        all_time_debts = _debt_total(Sale.objects.all())
        ctx["unpaid_total"] = all_time_debts["total"]
        ctx["unpaid_count"] = all_time_debts["count"]
        month_debts = _debt_total(month_sales)
        ctx["month_debts_total"] = month_debts["total"]
        ctx["month_debts_count"] = month_debts["count"]

        # 2. Today's sales summary by payment status
        today_sales = Sale.objects.filter(date_created__date=today)
        ctx["today_cash"] = _status_bucket(today_sales, Sale.CASH)
        ctx["today_mpesa"] = _status_bucket(today_sales, Sale.MPESA)
        ctx["today_unresolved"] = _status_bucket(today_sales, Sale.UNRESOLVED)
        ctx["today_unpaid"] = _debt_total(today_sales)
        ctx["today_total"] = {
            "total": today_sales.aggregate(total=Sum("amount"))["total"] or 0,
            "count": today_sales.count(),
        }

        # 2b. Debts paid today — money collected today against a debt that originated
        # on an EARLIER day (excludes same-day sales that got paid same-day, which are
        # already counted above as ordinary Cash/M-Pesa sales, not "debts"). Credit
        # payments are excluded — consuming existing credit isn't new money collected.
        debts_paid_today = DebtPayment.objects.filter(payment_date=today).exclude(sale__date_created__date=today)
        ctx["debts_paid_today_cash"] = (
            debts_paid_today.filter(payment_method=DebtPayment.CASH).aggregate(total=Sum("amount"))["total"] or 0
        )
        ctx["debts_paid_today_mpesa"] = (
            debts_paid_today.filter(payment_method=DebtPayment.MPESA).aggregate(total=Sum("amount"))["total"] or 0
        )

        # 3a. Monthly summary — last 6 months of sales totals
        six_months_start = _months_before(month_start, 5)
        monthly_rows = (
            Sale.objects.filter(date_created__date__gte=six_months_start)
            .annotate(month=TruncMonth("date_created"))
            .values("month")
            .annotate(total=Sum("amount"))
        )
        monthly_map = {row["month"].strftime("%Y-%m"): float(row["total"] or 0) for row in monthly_rows if row["month"]}
        monthly_summary = []
        for i in range(5, -1, -1):
            m = _months_before(month_start, i)
            monthly_summary.append({"label": m.strftime("%b %Y"), "total": monthly_map.get(m.strftime("%Y-%m"), 0)})
        ctx["monthly_summary"] = monthly_summary

        # 3b. Monthly payment distribution — this month's sales split by status
        ctx["monthly_distribution"] = {
            "cash": float(_status_bucket(month_sales, Sale.CASH)["total"] or 0),
            "mpesa": float(_status_bucket(month_sales, Sale.MPESA)["total"] or 0),
            "unpaid": float(_debt_total(month_sales)["total"] or 0),
            "unresolved": float(_status_bucket(month_sales, Sale.UNRESOLVED)["total"] or 0),
        }

        # 4. Weekly sales graph — last 7 days
        weekly_rows = (
            Sale.objects.filter(date_created__date__gte=week_start, date_created__date__lte=today)
            .annotate(day=TruncDate("date_created"))
            .values("day")
            .annotate(total=Sum("amount"))
        )
        weekly_map = {row["day"]: float(row["total"] or 0) for row in weekly_rows if row["day"]}
        weekly_sales = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            weekly_sales.append({"label": d.strftime("%a %d"), "total": weekly_map.get(d, 0)})
        ctx["weekly_sales"] = weekly_sales

        ctx["recent_sales"] = Sale.objects.prefetch_related("items__jar_type")[:8]

        # 5. Stock alerts — raw materials at or below their reorder level
        low_stock = RawMaterial.objects.filter(current_stock__lte=F("reorder_level")).order_by("name")
        ctx["low_stock_materials"] = low_stock[:6]
        ctx["low_stock_count"] = low_stock.count()

        # 6. Today's cash flow — cash/bank/M-Pesa account movement from posted GL entries.
        # Reads 0 if Finance isn't configured yet (no accounts flagged is_cash_account) —
        # this must never error just because Finance hasn't been set up.
        today_cash_lines = JournalLine.objects.filter(
            account__is_cash_account=True, entry__status=JournalEntry.POSTED, entry__date=today,
        )
        cash_flow_totals = today_cash_lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
        ctx["cash_flow_in"] = cash_flow_totals["debit"] or 0
        ctx["cash_flow_out"] = cash_flow_totals["credit"] or 0
        ctx["cash_flow_net"] = ctx["cash_flow_in"] - ctx["cash_flow_out"]

        # 7. Daily profit estimate — today's sales revenue minus today's expenses minus
        # an estimated cost of raw materials consumed by today's sales (from Inventory
        # stock movements), rather than relying on Finance being configured.
        today_expenses_total = (
            Expense.objects.filter(date_created__date=today).aggregate(total=Sum("amount"))["total"] or 0
        )
        today_sale_movements = StockMovement.objects.filter(
            movement_type=StockMovement.SALE, date_created__date=today,
        ).select_related("material")
        today_cogs_estimate = sum(
            abs(m.quantity) * (m.material.unit_cost or 0) for m in today_sale_movements
        )
        ctx["today_expenses_total"] = today_expenses_total
        ctx["today_cogs_estimate"] = today_cogs_estimate
        ctx["today_profit_estimate"] = ctx["today_total"]["total"] - today_expenses_total - today_cogs_estimate

        # 8. Daily sold litres
        today_items = SaleItem.objects.filter(sale__date_created__date=today).select_related("jar_type")
        ctx["today_water_liters"] = sum(item.quantity * item.jar_type.volume_in_liters for item in today_items)

        return ctx


class SalesReportView(ViewReportsMixin, TemplateView):
    template_name = "reports/sales_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Sale.objects.prefetch_related("items__jar_type")

        today = _today()
        sale_type = self.request.GET.get("type", "all")
        date_start = self.request.GET.get("date_start") or (today - timedelta(days=5)).isoformat()
        date_end = self.request.GET.get("date_end") or today.isoformat()

        if sale_type and sale_type != "all":
            qs = qs.filter(type=sale_type)
        qs = qs.filter(date_created__date__gte=date_start, date_created__date__lte=date_end)

        ctx["sales"] = qs
        ctx["total_amount"] = qs.aggregate(total=Sum("amount"))["total"] or 0
        ctx["filters"] = {
            "type": sale_type,
            "date_start": date_start,
            "date_end": date_end,
        }
        ctx["type_choices"] = Sale.TYPE_CHOICES
        return ctx
