from datetime import timedelta

from django.db import transaction
from django.db.models import Sum

from debts.models import DebtPayment
from mpesa.models import LegacyTransactionAllocation, MpesaTransaction
from sales.models import Sale

from .models import CashDepositAllocation


def _debts_paid(date_, method):
    """DebtPayment rows settling a genuinely pre-existing debt — the underlying Sale
    wasn't created the same day (see reports/views.py's "Debts Paid Today" card,
    which uses the identical definition). CREDIT-method payments are never included:
    consuming existing credit isn't new cash or M-Pesa money changing hands."""
    return (
        DebtPayment.objects.filter(payment_date=date_, payment_method=method)
        .exclude(sale__date_created__date=date_)
    )


def expected_cash(date_):
    sales_total = (
        Sale.objects.filter(date_created__date=date_, status=Sale.CASH).aggregate(t=Sum("amount"))["t"] or 0
    )
    debts_total = _debts_paid(date_, DebtPayment.CASH).aggregate(t=Sum("amount"))["t"] or 0
    return round(sales_total + debts_total, 2)


def expected_mpesa(date_):
    sales_total = (
        Sale.objects.filter(date_created__date=date_, status=Sale.MPESA).aggregate(t=Sum("amount"))["t"] or 0
    )
    debts_total = _debts_paid(date_, DebtPayment.MPESA).aggregate(t=Sum("amount"))["t"] or 0
    return round(sales_total + debts_total, 2)


def closing_balance(date_):
    """Safaricom's own running till balance (OrgAccountBalance) as of the end of
    `date_` — the OrgAccountBalance of the most recent transaction at or before that
    day's close, carried forward if no transaction happened that day. TransTime is a
    raw fixed-width 'YmdHis' string, so lexicographic ordering matches chronological
    ordering. Returns None if no balance data exists yet (e.g. before the till's
    first-ever transaction)."""
    cutoff = date_.strftime("%Y%m%d") + "235959"
    raw = (
        MpesaTransaction.objects.filter(TransTime__lte=cutoff)
        .exclude(OrgAccountBalance__isnull=True).exclude(OrgAccountBalance="")
        .order_by("-TransTime")
        .values_list("OrgAccountBalance", flat=True)
        .first()
    )
    if raw is None:
        return None
    try:
        return round(float(raw), 2)
    except (TypeError, ValueError):
        return None


def actual_mpesa(date_):
    """Net till inflow for `date_`, derived from the movement in Safaricom's own
    running balance (today's closing balance minus the previous day's) rather than
    summing individual TransAmount rows for the day. More resilient than a same-day
    transaction sum: still correct even if a transaction row is missing from
    mpesa_transactions, as long as the boundary transactions of each day carry an
    accurate OrgAccountBalance. Returns None if either day's balance is unavailable."""
    current = closing_balance(date_)
    previous = closing_balance(date_ - timedelta(days=1))
    if current is None or previous is None:
        return None
    return round(current - previous, 2)


def summary_for(date_, cash_collected=None):
    """cash_collected=None when no DailyReconciliation exists yet for date_ — the
    cash variance is then None (not entered yet), not a misleading 0. mpesa_variance
    is similarly None when the till balance movement can't be determined, rather than
    silently comparing against 0."""
    exp_cash = expected_cash(date_)
    exp_mpesa = expected_mpesa(date_)
    previous_balance = closing_balance(date_ - timedelta(days=1))
    current_balance = closing_balance(date_)
    act_mpesa = (
        round(current_balance - previous_balance, 2)
        if current_balance is not None and previous_balance is not None
        else None
    )
    return {
        "expected_cash": exp_cash,
        "cash_collected": cash_collected,
        "cash_variance": round(cash_collected - exp_cash, 2) if cash_collected is not None else None,
        "expected_mpesa": exp_mpesa,
        "previous_balance": previous_balance,
        "current_balance": current_balance,
        "actual_mpesa": act_mpesa,
        "mpesa_variance": round(act_mpesa - exp_mpesa, 2) if act_mpesa is not None else None,
    }


def candidate_deposit_transactions(record):
    """M-Pesa transactions that could be *this* day's cash-takings deposit: same
    amount as `cash_collected`, timestamped on or after the reconciliation date (the
    deposit happens after the cash is counted, never before), and not already spoken
    for — either as another day's deposit, or (partially or fully) allocated to a
    customer debt via mpesa's legacy allocation. Returns [] once a deposit is already
    allocated for this record, or before any cash count has been entered."""
    if record.cash_collected is None or hasattr(record, "deposit"):
        return []
    cutoff = record.date.strftime("%Y%m%d") + "000000"
    excluded_trans_ids = set(CashDepositAllocation.objects.values_list("trans_id", flat=True)) | set(
        LegacyTransactionAllocation.objects.values_list("trans_id", flat=True)
    )
    return list(
        MpesaTransaction.objects.filter(TransAmount=record.cash_collected, TransTime__gte=cutoff)
        .exclude(TransID__in=excluded_trans_ids)
        .order_by("TransTime")[:10]
    )


@transaction.atomic
def allocate_cash_deposit(record, trans_id, depositor_name, *, user=None):
    """Staff-confirmed match of an M-Pesa transaction to this day's cash deposit —
    never automatic, always one of the candidates services.py itself surfaced.
    `depositor_name` is who physically banked the cash, required and staff-supplied
    (typically pre-filled from the transaction's own registered name, but editable —
    see CashDepositAllocation's docstring)."""
    if hasattr(record, "deposit"):
        raise ValueError("This day's cash deposit has already been allocated.")
    depositor_name = depositor_name.strip()
    if not depositor_name:
        raise ValueError("The depositor's name is required.")
    txn = MpesaTransaction.objects.get(TransID=trans_id)
    return CashDepositAllocation.objects.create(
        reconciliation=record, trans_id=trans_id, amount=float(txn.TransAmount),
        depositor_name=depositor_name, allocated_by=user,
    )
