from datetime import timedelta

from django.db import transaction
from django.db.models import Q, Sum

from debts.models import DebtPayment
from mpesa.models import LegacyTransactionAllocation, MpesaTransaction
from mpesa.services.reconciliation import legacy_allocated_total
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


def cash_deposit_allocated_total(trans_id):
    """Sum already claimed against this M-Pesa transaction across every day's cash
    deposit it's been split into so far — the deposit-side counterpart of mpesa's
    own legacy_allocated_total() for customer debts."""
    return CashDepositAllocation.objects.filter(trans_id=trans_id).aggregate(t=Sum("amount"))["t"] or 0.0


def deposit_available_amount(txn):
    """How much of this M-Pesa transaction hasn't yet been claimed anywhere — by a
    customer-debt allocation (mpesa's legacy allocation) or by any day's cash
    deposit. A single transaction can be split across several days (an agent
    banking more than one day's takings in one lump sum), or between a debt and a
    deposit, as long as the total claimed across all of that never exceeds what the
    transaction actually carried."""
    claimed = legacy_allocated_total(txn.TransID) + cash_deposit_allocated_total(txn.TransID)
    return round(float(txn.TransAmount) - claimed, 2)


def _fully_claimed_trans_ids():
    """TransIDs with nothing left to allocate anywhere — excluded from candidates
    and search so staff aren't offered a transaction that's already fully spoken
    for. Bounded to transactions that appear in an allocation table at all; a
    transaction untouched by either table is implicitly fully available and never
    needs checking here."""
    trans_ids = set(CashDepositAllocation.objects.values_list("trans_id", flat=True)) | set(
        LegacyTransactionAllocation.objects.values_list("trans_id", flat=True)
    )
    fully_claimed = set()
    for trans_id in trans_ids:
        txn = MpesaTransaction.objects.filter(TransID=trans_id).first()
        if txn is not None and deposit_available_amount(txn) <= 0.01:
            fully_claimed.add(trans_id)
    return fully_claimed


def deposited_total(record):
    """Sum of every M-Pesa transaction (or partial slice of one) allocated as part
    of this day's cash deposit so far. 0 if none yet — distinct from
    deposit_variance()'s None, since "nothing deposited" is a real, summable
    amount, not an undefined comparison."""
    return record.deposits.aggregate(t=Sum("amount"))["t"] or 0.0


def _remaining_to_deposit(record):
    """What's still unaccounted for after existing deposits — what candidate
    matching and the search preview compare against, so a day banked in several
    tranches gets sensible suggestions for each remaining tranche rather than only
    ever matching the full day's cash_collected."""
    return record.cash_collected - deposited_total(record)


def _annotate_deposit_txn(txn, remaining):
    """Attaches the per-row fields the shared _deposit_txn_row.html template
    needs: how much of the transaction is still unclaimed anywhere (`.available`,
    since it may already be split across other days or a debt), a sensible starting
    point for the editable allocation amount (`.suggested_amount` — capped at
    whatever's actually available, never more), and `.variance` (available minus
    what's still remaining today) so staff can judge excess/deficit before
    allocating."""
    available = deposit_available_amount(txn)
    txn.available = available
    txn.suggested_amount = round(min(available, remaining), 2) if remaining > 0 else round(available, 2)
    txn.variance = round(available - remaining, 2)
    return txn


def candidate_deposit_transactions(record):
    """M-Pesa transactions that could be the *next* tranche of this day's
    cash-takings deposit: original amount matching whatever's still remaining after
    any deposits already allocated, timestamped on or after the reconciliation date
    (a deposit happens after the cash is counted, never before), and not already
    fully claimed elsewhere. [] once nothing remains, or before any cash count has
    been entered. A transaction bigger than what's needed here (e.g. one deposit
    covering several days) won't turn up as an exact match — that's what the search
    box below is for, letting staff allocate just part of it."""
    if record.cash_collected is None:
        return []
    remaining = round(_remaining_to_deposit(record), 2)
    if remaining <= 0:
        return []
    cutoff = record.date.strftime("%Y%m%d") + "000000"
    results = list(
        MpesaTransaction.objects.filter(TransAmount=remaining, TransTime__gte=cutoff)
        .exclude(TransID__in=_fully_claimed_trans_ids())
        .order_by("TransTime")[:10]
    )
    return [_annotate_deposit_txn(txn, remaining) for txn in results]


def search_deposit_transactions(record, query):
    """Manual fallback for the Cash Deposit search box — unlike
    candidate_deposit_transactions() this is NOT constrained to an exact amount
    match, since a real deposit can legitimately differ from what's still owed (an
    agent's fee, a rounding difference, another partial tranche), and a single large
    transaction can be *distributed* across several different days' reconciliations
    — staff pick how much of it to allocate here via the amount field
    allocate_cash_deposit() then records. Still constrained to on/after the
    reconciliation date and not already fully claimed elsewhere; requires a
    non-blank query — never lists the whole table."""
    query = (query or "").strip()
    if not query or record.cash_collected is None:
        return []
    remaining = round(_remaining_to_deposit(record), 2)
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
        .exclude(TransID__in=_fully_claimed_trans_ids())
        .order_by("-TransTime")[:15]
    )
    return [_annotate_deposit_txn(txn, remaining) for txn in results]


def valid_deposit_transaction(record, trans_id):
    """Whether `trans_id` is allocatable as (part of) this record's deposit right
    now — a real M-Pesa transaction, timestamped on/after the reconciliation date,
    with something still unclaimed on it. The POST handler validates against this
    rather than against candidate_deposit_transactions() alone, since a transaction
    confirmed via search is deliberately not amount-constrained and so isn't
    necessarily in that list."""
    if record.cash_collected is None:
        return None
    cutoff = record.date.strftime("%Y%m%d") + "000000"
    txn = MpesaTransaction.objects.filter(TransID=trans_id, TransTime__gte=cutoff).first()
    if txn is not None and deposit_available_amount(txn) > 0.01:
        return txn
    return None


def deposit_variance(record):
    """Excess/deficit between everything actually deposited so far (across every
    allocated transaction) and what cash_collected says should have been banked in
    total. None until at least one deposit is allocated — "nothing entered yet" is
    not the same as a KES 0 shortfall."""
    if not record.deposits.exists():
        return None
    return round(deposited_total(record) - record.cash_collected, 2)


@transaction.atomic
def allocate_cash_deposit(record, trans_id, depositor_name, amount, *, user=None):
    """Staff-confirmed match of (part of) an M-Pesa transaction to (part of) this
    day's cash deposit — never automatic, and never exclusive on either side: a day
    can have several of these if cash was banked in more than one tranche, and a
    single transaction can be split across several different days if it covered
    more than one day's takings in one lump sum. `trans_id` must already be
    validated via valid_deposit_transaction() by the caller. `amount` is how much of
    the transaction to credit to this day — capped here against what's actually
    still unclaimed on it, so two staff allocating from the same large deposit can
    never together claim more than it actually carried. `depositor_name` is who
    physically banked the cash, required and staff-supplied (typically pre-filled
    from the transaction's own registered name, but editable — see
    CashDepositAllocation's docstring)."""
    depositor_name = depositor_name.strip()
    if not depositor_name:
        raise ValueError("The depositor's name is required.")
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise ValueError("Enter a valid amount.")
    if amount <= 0:
        raise ValueError("The allocated amount must be greater than zero.")
    txn = MpesaTransaction.objects.select_for_update().get(TransID=trans_id)
    available = deposit_available_amount(txn)
    if amount > available + 0.01:
        raise ValueError(f"Only KES {available:,.2f} of this transaction is still unallocated.")
    return CashDepositAllocation.objects.create(
        reconciliation=record, trans_id=trans_id, amount=amount,
        depositor_name=depositor_name, allocated_by=user,
    )
