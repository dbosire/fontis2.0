from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import transaction

from .models import Account, AccountMapping, JournalEntry, JournalLine, JournalSequence


# See reports/views.py for why this can't just be timezone.localdate() (USE_TZ=False).
def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


class UnbalancedEntryError(Exception):
    pass


def _next_reference():
    seq = JournalSequence.objects.select_for_update().get(pk=JournalSequence.get_solo().pk)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"JE-{seq.last_number:05d}"


@transaction.atomic
def post_journal_entry(date, description, lines, *, source=JournalEntry.MANUAL, related_sale=None,
                        related_expense=None, related_payroll=None, related_bill=None,
                        related_petty_cash_voucher=None, user=None):
    """Create a balanced JournalEntry. `lines` is a list of (account, debit, credit)
    tuples — exactly one of debit/credit must be > 0 per line. Raises
    UnbalancedEntryError if the lines don't sum to zero (to the cent)."""
    clean_lines = [(account, round(debit or 0, 2), round(credit or 0, 2)) for account, debit, credit in lines]

    for account, debit, credit in clean_lines:
        if (debit > 0) == (credit > 0):
            raise UnbalancedEntryError(
                f"Line for account {account} must have exactly one of debit/credit set (got debit={debit}, credit={credit})."
            )

    total_debit = round(sum(debit for _, debit, _ in clean_lines), 2)
    total_credit = round(sum(credit for _, _, credit in clean_lines), 2)
    if round(total_debit - total_credit, 2) != 0:
        raise UnbalancedEntryError(f"Entry does not balance: debits={total_debit}, credits={total_credit}.")

    entry = JournalEntry.objects.create(
        date=date,
        reference=_next_reference(),
        description=description,
        source=source,
        related_sale=related_sale,
        related_expense=related_expense,
        related_payroll=related_payroll,
        related_bill=related_bill,
        related_petty_cash_voucher=related_petty_cash_voucher,
        created_by=user if user and getattr(user, "is_authenticated", False) else None,
    )
    JournalLine.objects.bulk_create([
        JournalLine(entry=entry, account=account, debit=debit, credit=credit)
        for account, debit, credit in clean_lines
    ])
    return entry


def void_journal_entry(entry, user=None):
    if entry.status == JournalEntry.VOID:
        return entry
    entry.status = JournalEntry.VOID
    entry.voided_at = datetime.now(ZoneInfo("Africa/Nairobi")).replace(tzinfo=None)
    entry.save(update_fields=["status", "voided_at"])
    return entry


@transaction.atomic
def repost_for_source(*, source_type, source_field, source_object, date, description, lines, user=None):
    """Void any existing live JournalEntry for this source object, then post a fresh
    one reflecting its current state. Used for every create/edit/status-change coming
    from Sales/Expenses/Payroll/Bills so the ledger stays an immutable, audit-safe
    trail (corrections happen via void+repost, never by editing history in place).

    Filters on `source=source_type` in addition to the FK, not just the FK alone —
    Bill and BillPayment can both carry `related_bill` pointing at the same Bill, and
    without the source filter a new BillPayment would incorrectly void the Bill's own
    entry (or a sibling payment's entry) just because they share that FK value.
    """
    existing = (
        JournalEntry.objects.select_for_update()
        .filter(**{source_field: source_object, "status": JournalEntry.POSTED, "source": source_type})
        .first()
    )
    if existing:
        void_journal_entry(existing, user=user)

    if not lines:
        return None

    return post_journal_entry(
        date, description, lines, source=source_type, user=user,
        **{source_field: source_object},
    )


def void_for_source(*, source_field, source_object, user=None):
    entry = JournalEntry.objects.filter(**{source_field: source_object, "status": JournalEntry.POSTED}).first()
    if entry:
        void_journal_entry(entry, user=user)
    return entry


# ---------------------------------------------------------------------------
# Auto-posting hooks (Phase B)
# ---------------------------------------------------------------------------

def _sale_debit_account(mapping, sale):
    from sales.models import Sale
    if sale.status == Sale.CASH:
        return mapping.cash_account
    if sale.status == Sale.MPESA:
        return mapping.mpesa_account
    # UNPAID and UNRESOLVED both represent money not yet collected.
    return mapping.accounts_receivable_account


def sync_journal_for_sale(sale, user=None):
    mapping = AccountMapping.get_solo()
    debit_account = _sale_debit_account(mapping, sale)
    credit_account = mapping.sales_revenue_account

    if not debit_account or not credit_account or not sale.amount:
        return void_for_source(source_field="related_sale", source_object=sale, user=user)

    lines = [(debit_account, sale.amount, 0), (credit_account, 0, sale.amount)]
    return repost_for_source(
        source_type=JournalEntry.SALE, source_field="related_sale", source_object=sale,
        date=sale.date_created.date(), description=f"Sale #{sale.pk} — {sale.customer_name}",
        lines=lines, user=user,
    )


def void_journal_for_sale(sale, user=None):
    return void_for_source(source_field="related_sale", source_object=sale, user=user)


def _expense_credit_account(mapping, expense):
    from expenses.models import Expense
    if expense.status == Expense.CASH:
        return mapping.cash_account
    if expense.status == Expense.MPESA:
        return mapping.mpesa_account
    return mapping.accounts_payable_account


def _expense_debit_account(mapping, expense):
    if expense.employee_id:
        return mapping.employee_advances_account
    from .models import ExpenseCategoryAccountMapping
    category_mapping = ExpenseCategoryAccountMapping.objects.filter(category=expense.category).first()
    if category_mapping:
        return category_mapping.account
    return mapping.default_expense_account


def sync_journal_for_expense(expense, user=None):
    mapping = AccountMapping.get_solo()
    debit_account = _expense_debit_account(mapping, expense)
    credit_account = _expense_credit_account(mapping, expense)

    if not debit_account or not credit_account or not expense.amount:
        return void_for_source(source_field="related_expense", source_object=expense, user=user)

    lines = [(debit_account, expense.amount, 0), (credit_account, 0, expense.amount)]
    return repost_for_source(
        source_type=JournalEntry.EXPENSE, source_field="related_expense", source_object=expense,
        date=expense.date_created.date(), description=f"Expense #{expense.pk} — {expense.expense_name}",
        lines=lines, user=user,
    )


def void_journal_for_expense(expense, user=None):
    return void_for_source(source_field="related_expense", source_object=expense, user=user)


def sync_journal_for_payroll(payroll, user=None):
    """Only call this on a transition to Payroll.PAID. Posts gross pay across four
    lines rather than just the net cash cost — see finance module design notes: a
    net-pay-only entry would silently double-count against employee-tagged Expenses
    that were already posted to employee_advances_account when they were created."""
    mapping = AccountMapping.get_solo()
    gross = round(payroll.basic_salary + payroll.allowances + payroll.commission_earned, 2)

    lines = [(mapping.salaries_expense_account, gross, 0)]
    if payroll.expense_deductions:
        lines.append((mapping.employee_advances_account, 0, round(payroll.expense_deductions, 2)))
    if payroll.other_deductions:
        lines.append((mapping.payroll_deductions_payable_account, 0, round(payroll.other_deductions, 2)))
    net_pay = round(payroll.net_pay, 2)
    if net_pay:
        lines.append((mapping.cash_account, 0, net_pay))

    if any(account is None for account, _, _ in lines) or not gross:
        return void_for_source(source_field="related_payroll", source_object=payroll, user=user)

    return repost_for_source(
        source_type=JournalEntry.PAYROLL, source_field="related_payroll", source_object=payroll,
        date=payroll.paid_date or _today(),
        description=f"Payroll — {payroll.employee.get_full_name()} ({payroll.period_start} - {payroll.period_end})",
        lines=lines, user=user,
    )


def void_journal_for_payroll(payroll, user=None):
    return void_for_source(source_field="related_payroll", source_object=payroll, user=user)


# ---------------------------------------------------------------------------
# Accounts Payable hooks (Phase D) — Bill creation is void-and-repost keyed on
# (related_bill, source=BILL); each BillPayment is its own fresh entry (source=
# BILL_PAYMENT) since a bill can have many payments, not one mutable state.
# ---------------------------------------------------------------------------

def sync_journal_for_bill(bill, user=None):
    mapping = AccountMapping.get_solo()
    credit_account = mapping.accounts_payable_account
    if not credit_account or not bill.expense_account or not bill.amount:
        return void_for_source(source_field="related_bill", source_object=bill, user=user)

    lines = [(bill.expense_account, bill.amount, 0), (credit_account, 0, bill.amount)]
    return repost_for_source(
        source_type=JournalEntry.BILL, source_field="related_bill", source_object=bill,
        date=bill.bill_date, description=f"Bill {bill.bill_number or bill.pk} — {bill.supplier or 'supplier'}",
        lines=lines, user=user,
    )


def void_journal_for_bill(bill, user=None):
    return void_for_source(source_field="related_bill", source_object=bill, user=user)


def post_journal_for_bill_payment(payment, user=None):
    mapping = AccountMapping.get_solo()
    debit_account = mapping.accounts_payable_account
    # AccountMapping has no dedicated "default bank" slot (BankAccount in Phase C can
    # be one of several) — bank-method payments fall back to cash_account for v1;
    # Bank Reconciliation still works independently by matching statement lines
    # against whichever cash-type account's journal lines actually apply.
    credit_account = {
        payment.CASH: mapping.cash_account,
        payment.MPESA: mapping.mpesa_account,
        payment.BANK: mapping.cash_account,
    }.get(payment.payment_method)

    if not debit_account or not credit_account or not payment.amount:
        return None

    lines = [(debit_account, payment.amount, 0), (credit_account, 0, payment.amount)]
    return post_journal_entry(
        payment.payment_date, f"Payment on bill {payment.bill.bill_number or payment.bill.pk}",
        lines, source=JournalEntry.BILL_PAYMENT, related_bill=payment.bill, user=user,
    )


# ---------------------------------------------------------------------------
# Petty Cash hooks (Phase C)
# ---------------------------------------------------------------------------

def post_journal_for_petty_cash_voucher(voucher, user=None):
    mapping = AccountMapping.get_solo()
    from .models import ExpenseCategoryAccountMapping
    category_mapping = ExpenseCategoryAccountMapping.objects.filter(category=voucher.category).first()
    debit_account = category_mapping.account if category_mapping else mapping.default_expense_account

    if not debit_account or not voucher.amount:
        return None

    lines = [(debit_account, voucher.amount, 0), (voucher.fund.gl_account, 0, voucher.amount)]
    return post_journal_entry(
        voucher.date, f"Petty cash — {voucher.description}", lines,
        source=JournalEntry.PETTY_CASH, related_petty_cash_voucher=voucher, user=user,
    )


def post_journal_for_petty_cash_replenishment(fund, amount, date, source_account, user=None):
    if not amount:
        return None
    lines = [(fund.gl_account, amount, 0), (source_account, 0, amount)]
    return post_journal_entry(
        date, f"Replenish petty cash fund — {fund.name}", lines, source=JournalEntry.PETTY_CASH, user=user,
    )


# ---------------------------------------------------------------------------
# Depreciation hooks (Phase F)
# ---------------------------------------------------------------------------

def run_depreciation(period, user=None):
    """Create DepreciationEntry rows + one combined JournalEntry for every active,
    not-yet-fully-depreciated FixedAsset that doesn't already have an entry for this
    period. Idempotent per (asset, period) via the model's UniqueConstraint — safe to
    call twice for the same month."""
    from .models import DepreciationEntry, FixedAsset

    lines = []
    created_entries = []
    assets = FixedAsset.objects.filter(disposed=False)
    for asset in assets:
        if asset.is_fully_depreciated:
            continue
        if DepreciationEntry.objects.filter(asset=asset, period=period).exists():
            continue
        remaining = round(asset.cost - asset.salvage_value - asset.accumulated_depreciation, 2)
        amount = min(asset.monthly_depreciation, remaining)
        if amount <= 0:
            continue
        entry = DepreciationEntry.objects.create(asset=asset, period=period, amount=amount)
        created_entries.append(entry)
        lines.append((asset.depreciation_expense_account, amount, 0))
        lines.append((asset.accumulated_depreciation_account, 0, amount))

    if not lines:
        return created_entries, None

    journal_entry = post_journal_entry(
        period, f"Depreciation run — {period:%B %Y}", lines, source=JournalEntry.DEPRECIATION, user=user,
    )
    return created_entries, journal_entry
