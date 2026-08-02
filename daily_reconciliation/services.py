from datetime import timedelta

from django.db import transaction
from django.db.models import Q, Sum

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


def _excluded_deposit_trans_ids():
    """TransIDs already spoken for — either as another day's cash deposit, or
    (partially or fully) allocated to a customer debt via mpesa's legacy
    allocation — so neither the auto-matched candidates nor search can double-offer
    a transaction that's already been claimed elsewhere."""
    return set(CashDepositAllocation.objects.values_list("trans_id", flat=True)) | set(
        LegacyTransactionAllocation.objects.values_list("trans_id", flat=True)
    )


def deposited_total(record):
    """Sum of every M-Pesa transaction allocated as (part of) this day's cash
    deposit so far. 0 if none yet — distinct from deposit_variance()'s None, since
    "nothing deposited" is a real, summable amount, not an undefined comparison."""
    return record.deposits.aggregate(t=Sum("amount"))["t"] or 0.0


def _remaining_to_deposit(record):
    """What's still unaccounted for after existing deposits — what candidate
    matching and the search preview compare against, so a day banked in several
    tranches gets sensible suggestions for each remaining tranche rather than only
    ever matching the full day's cash_collected."""
    return record.cash_collected - deposited_total(record)


def candidate_deposit_transactions(record):
    """M-Pesa transactions that could be the *next* tranche of this day's
    cash-takings deposit: amount matching whatever's still remaining after any
    deposits already allocated, timestamped on or after the reconciliation date (a
    deposit happens after the cash is counted, never before), and not already spoken
    for. [] once nothing remains, or before any cash count has been entered. Each
    result carries a `.variance` of 0 — these are exact matches against the
    remaining balance by construction — so candidate and search rows can share one
    template."""
    if record.cash_collected is None:
        return []
    remaining = _remaining_to_deposit(record)
    cutoff = record.date.strftime("%Y%m%d") + "000000"
    results = list(
        MpesaTransaction.objects.filter(TransAmount=remaining, TransTime__gte=cutoff)
        .exclude(TransID__in=_excluded_deposit_trans_ids())
        .order_by("TransTime")[:10]
    )
    for txn in results:
        txn.variance = 0.0
    return results


def search_deposit_transactions(record, query):
    """Manual fallback for the Cash Deposit search box — unlike
    candidate_deposit_transactions() this is NOT constrained to an exact amount
    match, since a real deposit can legitimately differ from what's still owed (an
    agent's fee, a rounding difference, another partial tranche). Each result's
    `.variance` (its amount minus what's still remaining after existing deposits)
    lets staff judge that difference before allocating rather than being surprised
    after. Still constrained to on/after the reconciliation date and not already
    allocated elsewhere; requires a non-blank query — never lists the whole table."""
    query = (query or "").strip()
    if not query or record.cash_collected is None:
        return []
    remaining = _remaining_to_deposit(record)
    cutoff = record.date.strftime("%Y%m%d") + "000000"
    filters = (
        Q(TransID__icontains=query) | Q(MSISDN__icontains=query) | Q(FirstName__icontains=query)
        | Q(MiddleName__icontains=query) | Q(LastName__icontains=query) | Q(BillRefNumber__icontains=query)
    )
    try:
        filters |= Q(TransAmount=float(query))
    except ValueError:
        pass
    results = list(
        MpesaTransaction.objects.filter(filters, TransTime__gte=cutoff)
        .exclude(TransID__in=_excluded_deposit_trans_ids())
        .order_by("-TransTime")[:15]
    )
    for txn in results:
        txn.variance = round(float(txn.TransAmount) - remaining, 2)
    return results


def valid_deposit_transaction(record, trans_id):
    """Whether `trans_id` is allocatable as (part of) this record's deposit right
    now — a real M-Pesa transaction, timestamped on/after the reconciliation date,
    not already claimed elsewhere. The POST handler validates against this rather
    than against candidate_deposit_transactions() alone, since a transaction
    confirmed via search is deliberately not amount-constrained and so isn't
    necessarily in that list."""
    if record.cash_collected is None:
        return None
    cutoff = record.date.strftime("%Y%m%d") + "000000"
    return (
        MpesaTransaction.objects.filter(TransID=trans_id, TransTime__gte=cutoff)
        .exclude(TransID__in=_excluded_deposit_trans_ids())
        .first()
    )


def deposit_variance(record):
    """Excess/deficit between everything actually deposited so far (across every
    allocated transaction) and what cash_collected says should have been banked in
    total. None until at least one deposit is allocated — "nothing entered yet" is
    not the same as a KES 0 shortfall."""
    if not record.deposits.exists():
        return None
    return round(deposited_total(record) - record.cash_collected, 2)


@transaction.atomic
def allocate_cash_deposit(record, trans_id, depositor_name, *, user=None):
    """Staff-confirmed match of an M-Pesa transaction to (part of) this day's cash
    deposit — never automatic, and never exclusive: a day can have several of these
    if cash was banked in more than one tranche. `trans_id` must already be
    validated via valid_deposit_transaction() by the caller. `depositor_name` is who
    physically banked the cash, required and staff-supplied (typically pre-filled
    from the transaction's own registered name, but editable — see
    CashDepositAllocation's docstring)."""
    depositor_name = depositor_name.strip()
    if not depositor_name:
        raise ValueError("The depositor's name is required.")
    txn = MpesaTransaction.objects.get(TransID=trans_id)
    return CashDepositAllocation.objects.create(
        reconciliation=record, trans_id=trans_id, amount=float(txn.TransAmount),
        depositor_name=depositor_name, allocated_by=user,
    )
