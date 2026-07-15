from django.db import transaction

from crm.services.loyalty import award_points_for_sale
from finance.services import sync_journal_for_sale
from sales.models import Sale

from .models import DebtPayment


@transaction.atomic
def record_debt_payment(sale, *, amount, payment_date, payment_method, notes="", user=None):
    """Records a payment against an UNPAID/PARTIAL Sale. If it fully settles the
    balance, flips the Sale to CASH/MPESA and fires the *same* side effects a full
    payment already triggers elsewhere (see debts/views.py::DebtBulkUpdateStatusView,
    mpesa/services/reconciliation.py::confirm_payment_link) — so a partial-then-final
    payment ends up identical to a same-day full payment. Otherwise just records the
    payment and leaves the Sale PARTIAL.

    Deliberately posts no GL entry for an interim (non-settling) payment — see the
    plan notes on finance/services.py::_sale_debit_account for why. Raises ValueError
    on a non-positive amount or one that exceeds the current balance (mirrors the
    over-allocation guard in mpesa/services/reconciliation.py::allocate_legacy_transaction).
    """
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status not in (Sale.UNPAID, Sale.PARTIAL):
        raise ValueError("This debt is already settled.")
    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")
    balance = sale.balance_due
    if amount > balance + 0.01:
        raise ValueError(
            f"Payment of KES {amount:,.2f} exceeds the outstanding balance of KES {balance:,.2f}."
        )

    DebtPayment.objects.create(
        sale=sale, amount=amount, payment_date=payment_date,
        payment_method=payment_method, notes=notes, recorded_by=user,
    )

    new_balance = round(balance - amount, 2)
    if new_balance <= 0.01:
        sale.status = Sale.CASH if payment_method == DebtPayment.CASH else Sale.MPESA
        sale.save(update_fields=["status"])
        award_points_for_sale(sale, user=user)
        sync_journal_for_sale(sale, user=user)
    else:
        sale.status = Sale.PARTIAL
        sale.save(update_fields=["status"])

    return sale
