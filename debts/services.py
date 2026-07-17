from django.db import transaction
from django.db.models import Sum

from crm.services.loyalty import award_points_for_sale
from finance.services import sync_journal_for_sale
from sales.models import Sale

from .models import CustomerCredit, DebtPayment


def customer_credit_balance(customer_name):
    return round(
        CustomerCredit.objects.filter(customer_name__iexact=customer_name.strip())
        .aggregate(total=Sum("amount"))["total"]
        or 0,
        2,
    )


@transaction.atomic
def record_debt_payment(sale, *, amount, payment_date, payment_method, notes="", user=None):
    """Records a payment against an UNPAID/PARTIAL Sale. If it fully settles the
    balance, flips the Sale to CASH/MPESA/CREDIT and fires the *same* side effects a
    full payment already triggers elsewhere (see debts/views.py::DebtBulkUpdateStatusView,
    mpesa/services/reconciliation.py::confirm_payment_link) — so a partial-then-final
    payment ends up identical to a same-day full payment. Otherwise just records the
    payment and leaves the Sale PARTIAL.

    Deliberately posts no GL entry for an interim (non-settling) payment, or ever for
    the credit mechanism itself — see the plan notes on
    finance/services.py::_sale_debit_account for why (a CREDIT-settled sale still gets
    the same Dr AR/Cr Revenue entry every sale gets at creation, it just never reposts
    out of AR the way CASH/MPESA settlement does).

    Two different overpayment behaviours depending on payment_method:
    - CASH/MPESA: any amount beyond the sale's balance is capped there, and the excess
      becomes a new CustomerCredit (source=Overpayment) for this customer — no error.
    - CREDIT: the amount is validated against the customer's *actual* available
      credit (raises ValueError if it would exceed it — this is the old "overpayment"
      guard's spirit, just scoped to credit specifically), and consumes that credit via
      a matching negative CustomerCredit (source=Applied).
    """
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status not in (Sale.UNPAID, Sale.PARTIAL):
        raise ValueError("This debt is already settled.")
    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    if payment_method == DebtPayment.CREDIT:
        available = customer_credit_balance(sale.customer_name)
        if amount > available + 0.01:
            raise ValueError(
                f"{sale.customer_name} only has KES {available:,.2f} in available credit."
            )

    balance = sale.balance_due
    applied = min(amount, balance)
    excess = round(amount - applied, 2)

    DebtPayment.objects.create(
        sale=sale, amount=applied, payment_date=payment_date,
        payment_method=payment_method, notes=notes, recorded_by=user,
    )

    if payment_method == DebtPayment.CREDIT:
        CustomerCredit.objects.create(
            customer_name=sale.customer_name, amount=-applied, payment_date=payment_date,
            source=CustomerCredit.APPLIED, related_sale=sale,
            notes=notes or f"Applied to Sale #{sale.pk}", recorded_by=user,
        )

    new_balance = round(balance - applied, 2)
    if new_balance <= 0.01:
        if payment_method == DebtPayment.CREDIT:
            sale.status = Sale.CREDIT
        elif payment_method == DebtPayment.CASH:
            sale.status = Sale.CASH
        else:
            sale.status = Sale.MPESA
        sale.save(update_fields=["status"])
        award_points_for_sale(sale, user=user)
        sync_journal_for_sale(sale, user=user)
    else:
        sale.status = Sale.PARTIAL
        sale.save(update_fields=["status"])

    if excess > 0.01:
        # Only CASH/MPESA can land here — a CREDIT payment is already capped by the
        # available-credit check above, so it can never generate its own excess.
        CustomerCredit.objects.create(
            customer_name=sale.customer_name, amount=excess, payment_date=payment_date,
            source=CustomerCredit.OVERPAYMENT, payment_method=payment_method, related_sale=sale,
            notes=f"Overpayment on Sale #{sale.pk}", recorded_by=user,
        )

    return sale


def record_prepayment(customer_name, *, amount, payment_date, payment_method, notes="", user=None):
    """Records cash received from a customer with no debt to apply it to yet — pure
    credit, no Sale involved."""
    if amount <= 0:
        raise ValueError("Prepayment amount must be greater than zero.")
    return CustomerCredit.objects.create(
        customer_name=customer_name.strip(), amount=amount, payment_date=payment_date,
        source=CustomerCredit.PREPAYMENT, payment_method=payment_method, notes=notes, recorded_by=user,
    )
