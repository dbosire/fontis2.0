import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum

from crm.services.loyalty import award_points_for_sale
from finance.services import sync_journal_for_sale
from sales.models import Sale

from ..models import LegacyTransactionAllocation, MpesaC2BTransaction, PaymentLink, STKPushAttempt
from .daraja import normalize_phone_number

logger = logging.getLogger(__name__)


# USE_TZ=False project-wide — naive local time only, see mpesa/models.py::_now().
def _now():
    return datetime.now(ZoneInfo("Africa/Nairobi")).replace(tzinfo=None)


@transaction.atomic
def confirm_payment_link(payment_link_id, *, via, receipt="", user=None):
    """The single locked chokepoint every payment-confirmation path funnels through
    (STK callback success, C2B auto-match, staff manual match). Takes an id — not an
    already-fetched instance — so callers do their own lookups/matching *outside* this
    transaction, keeping the row lock held for the shortest possible window.

    select_for_update() closes the race where an STK callback and a C2B confirmation
    for the same link arrive close together: without it, both requests could read
    status=PENDING before either writes PAID, double-processing the linked sales
    (double GL entries, double loyalty points). With the lock, whichever request gets
    here first wins; the second sees a non-PENDING status and no-ops.

    Also checks is_expired as part of the gate — a late-arriving webhook for a link
    that's since expired must not silently confirm it.
    """
    link = PaymentLink.objects.select_for_update().get(pk=payment_link_id)
    if link.status != PaymentLink.PENDING or link.is_expired:
        return link

    link.status = PaymentLink.PAID
    link.paid_at = _now()
    link.confirmed_via = via
    link.mpesa_receipt_number = receipt
    link.save(update_fields=["status", "paid_at", "confirmed_via", "mpesa_receipt_number"])

    # Only touch sales still UNPAID at confirmation time — mirrors
    # debts/views.py::DebtBulkUpdateStatusView exactly, so a sale independently cleared
    # by staff while the link was pending isn't double-counted. If that leaves the
    # payer having paid for more than the still-unpaid subset, that's accepted,
    # intentional behaviour — no overpayment/refund tracking exists or is in scope.
    matched_ids = list(link.sales.filter(status=Sale.UNPAID).values_list("pk", flat=True))
    Sale.objects.filter(pk__in=matched_ids).update(status=Sale.MPESA)
    for sale in Sale.objects.filter(pk__in=matched_ids):
        award_points_for_sale(sale, user=user)
        sync_journal_for_sale(sale, user=user)

    return link


def handle_stk_callback(payload):
    """Parses a Daraja STK Push callback body. Never raises — any error is logged and
    swallowed, since the caller must always ack Daraja regardless of internal outcome
    (returning anything else invites aggressive retries, not correctness)."""
    try:
        stk_callback = payload["Body"]["stkCallback"]
        checkout_request_id = stk_callback["CheckoutRequestID"]
        merchant_request_id = stk_callback.get("MerchantRequestID", "")
        result_code = stk_callback["ResultCode"]
        result_desc = stk_callback.get("ResultDesc", "")
    except (KeyError, TypeError):
        logger.error("mpesa: malformed STK callback payload: %r", payload)
        return

    attempt = STKPushAttempt.objects.filter(checkout_request_id=checkout_request_id).first()
    if attempt is None and merchant_request_id:
        # Defensive fallback — checkout_request_id is the documented, reliable field,
        # but if a payload is ever missing it, don't silently drop the callback.
        attempt = STKPushAttempt.objects.filter(merchant_request_id=merchant_request_id).first()
    if attempt is None:
        logger.error("mpesa: STK callback for unknown checkout_request_id=%s", checkout_request_id)
        return

    if attempt.status == STKPushAttempt.SUCCESS:
        return  # already processed — idempotent against Daraja's callback retries

    attempt.result_code = str(result_code)
    attempt.result_desc = result_desc

    if result_code != 0:
        attempt.status = STKPushAttempt.CANCELLED if result_code == 1032 else STKPushAttempt.FAILED
        attempt.save(update_fields=["status", "result_code", "result_desc"])
        return

    metadata = {
        item.get("Name"): item.get("Value")
        for item in stk_callback.get("CallbackMetadata", {}).get("Item", [])
    }
    receipt = str(metadata.get("MpesaReceiptNumber", ""))
    attempt.status = STKPushAttempt.SUCCESS
    attempt.mpesa_receipt_number = receipt
    attempt.save(update_fields=["status", "result_code", "result_desc", "mpesa_receipt_number"])

    confirm_payment_link(attempt.payment_link_id, via=PaymentLink.STK, receipt=receipt)


def handle_c2b_confirmation(payload):
    """Parses a Daraja C2B Confirmation payload (the 'Direct payment' path — customer
    paid the Till manually, with no prior STK request to reference). Never raises."""
    try:
        trans_id = payload["TransID"]
    except (KeyError, TypeError):
        logger.error("mpesa: malformed C2B confirmation payload: %r", payload)
        return None

    import json
    transaction_row, created = MpesaC2BTransaction.objects.get_or_create(
        trans_id=trans_id,
        defaults={
            "trans_time": payload.get("TransTime", ""),
            "trans_amount": float(payload.get("TransAmount") or 0),
            "business_short_code": payload.get("BusinessShortCode", ""),
            "bill_ref_number": payload.get("BillRefNumber", ""),
            "msisdn": payload.get("MSISDN", ""),
            "first_name": payload.get("FirstName", ""),
            "middle_name": payload.get("MiddleName", ""),
            "last_name": payload.get("LastName", ""),
            "raw_payload": json.dumps(payload)[:8000],
        },
    )

    if not created:
        # A Daraja retry of a confirmation we've already seen — ack and do nothing
        # further, so a retry can never re-trigger matching/notes/etc.
        return transaction_row

    _attempt_c2b_match(transaction_row)
    return transaction_row


def _attempt_c2b_match(transaction_row):
    """Auto-match rule: amount AND a non-blank matching phone number, never amount
    alone. Round KES amounts collide often for a water-refill business — matching on
    amount only risks crediting a *different* customer's debt with someone else's
    money, which is a financial-correctness bug, not just a UX rough edge. A link with
    no phone number captured is never auto-matched, full stop — it always lands in the
    manual reconciliation queue.

    Also checks already-PAID links (not just PENDING ones): a C2B confirmation can
    legitimately arrive for a link the customer *also* just paid via STK moments
    earlier — that must land as DUPLICATE with the link still recorded for audit, not
    silently fall through to UNMATCHED just because it's no longer PENDING.
    """
    normalized_payer = normalize_phone_number(transaction_row.msisdn)
    if not normalized_payer:
        return

    def _phone_matches(qs):
        candidates = list(qs.filter(amount=transaction_row.trans_amount).exclude(phone_number=""))
        return [c for c in candidates if normalize_phone_number(c.phone_number) == normalized_payer]

    pending_matches = _phone_matches(PaymentLink.objects.filter(status=PaymentLink.PENDING))
    if len(pending_matches) == 1:
        link = pending_matches[0]
        confirm_payment_link(link.pk, via=PaymentLink.DIRECT, receipt=transaction_row.trans_id)
        link.refresh_from_db()
        transaction_row.matched_payment_link = link
        transaction_row.status = MpesaC2BTransaction.MATCHED if link.status == PaymentLink.PAID else MpesaC2BTransaction.DUPLICATE
        transaction_row.save(update_fields=["matched_payment_link", "status"])
        return
    if len(pending_matches) > 1:
        return  # ambiguous — leave UNMATCHED for staff

    paid_matches = _phone_matches(PaymentLink.objects.filter(status=PaymentLink.PAID))
    if len(paid_matches) == 1:
        transaction_row.matched_payment_link = paid_matches[0]
        transaction_row.status = MpesaC2BTransaction.DUPLICATE
        transaction_row.save(update_fields=["matched_payment_link", "status"])
        return

    # No PENDING match, no PAID match (or ambiguous even among paid ones) — leave
    # UNMATCHED for staff rather than guessing.


def manual_match(c2b_transaction, payment_link, user=None):
    """Staff-driven reconciliation for a transaction that couldn't be auto-matched —
    mirrors finance/views.py::BankReconciliationView's click-to-match pattern."""
    confirm_payment_link(payment_link.pk, via=PaymentLink.MANUAL, receipt=c2b_transaction.trans_id, user=user)
    payment_link.refresh_from_db()
    c2b_transaction.matched_payment_link = payment_link
    c2b_transaction.status = (
        MpesaC2BTransaction.MATCHED if payment_link.status == PaymentLink.PAID else MpesaC2BTransaction.DUPLICATE
    )
    c2b_transaction.save(update_fields=["matched_payment_link", "status"])
    return c2b_transaction


def legacy_allocated_total(trans_id):
    return LegacyTransactionAllocation.objects.filter(trans_id=trans_id).aggregate(total=Sum("amount"))["total"] or 0.0


@transaction.atomic
def allocate_legacy_transaction(trans_id, trans_amount, sale_ids, *, user=None):
    """Marks the given (still-UNPAID) Sales as paid via M-Pesa and records that this
    legacy `MpesaTransaction` — which predates PaymentLink/STK/C2B and has no built-in
    way to reference what it paid for — covered them. One transaction can be split
    across several sales/customers in one call, which is the whole point: this is for
    a lump-sum payment (e.g. an agent depositing several customers' cash-collected
    dues as one M-Pesa transaction) that doesn't correspond to any single debt.

    Blocks (rather than silently truncating) if the selected sales' total would push
    allocations for this transaction past its own amount — the same financial-
    correctness rule as everywhere else in this module: never credit debts with money
    the transaction didn't actually carry. select_for_update() closes the same
    double-submit race confirm_payment_link() guards against.
    """
    trans_amount = float(trans_amount)
    already_allocated = legacy_allocated_total(trans_id)
    remaining = trans_amount - already_allocated

    sales = list(Sale.objects.select_for_update().filter(pk__in=sale_ids, status=Sale.UNPAID))
    selected_total = sum(sale.amount for sale in sales)
    if selected_total > remaining + 0.01:
        raise ValueError(
            f"Selected debts total KES {selected_total:,.2f}, which exceeds the "
            f"KES {remaining:,.2f} still unallocated on this transaction."
        )

    for sale in sales:
        sale.status = Sale.MPESA
        sale.save(update_fields=["status"])
        LegacyTransactionAllocation.objects.create(trans_id=trans_id, sale=sale, amount=sale.amount, allocated_by=user)
        award_points_for_sale(sale, user=user)
        sync_journal_for_sale(sale, user=user)

    return sales
