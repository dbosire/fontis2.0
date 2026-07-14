from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import transaction

from inventory.models import Purchase, StockMovement
from inventory.services import record_stock_movement

from .models import GoodsReceiptLine, PurchaseOrder, PurchaseRequest


# See reports/views.py for why this can't just be timezone.localdate() (USE_TZ=False).
def _now():
    return datetime.now(ZoneInfo("Africa/Nairobi")).replace(tzinfo=None)


def decide_purchase_request(request_obj, *, approved, user, rejection_reason=""):
    """Approve or reject a pending PurchaseRequest. Idempotent no-op if the request
    isn't currently pending, so a stale double-submit can't flip an already-decided
    request back and forth."""
    if request_obj.status != PurchaseRequest.PENDING:
        return request_obj

    request_obj.status = PurchaseRequest.APPROVED if approved else PurchaseRequest.REJECTED
    request_obj.approved_by = user if user and user.is_authenticated else None
    request_obj.date_decided = _now()
    if not approved:
        request_obj.rejection_reason = rejection_reason
    request_obj.save(update_fields=["status", "approved_by", "date_decided", "rejection_reason"])
    return request_obj


@transaction.atomic
def create_purchase_order_from_request(request_obj, *, supplier, order_date, expected_delivery_date=None, user=None):
    """Build a draft PurchaseOrder pre-filled with one line per PurchaseRequestLine
    (unit_price left at 0 — the requester doesn't price items, the buyer does when
    editing the PO). Marks the source request CONVERTED so it can't be converted twice."""
    if request_obj.status != PurchaseRequest.APPROVED:
        raise ValueError("Only an approved purchase request can be converted to a purchase order.")

    order = PurchaseOrder.objects.create(
        supplier=supplier,
        related_request=request_obj,
        order_date=order_date,
        expected_delivery_date=expected_delivery_date,
        created_by=user,
    )
    for line in request_obj.lines.all():
        order.lines.create(material=line.material, quantity_ordered=line.quantity, unit_price=0)

    request_obj.status = PurchaseRequest.CONVERTED
    request_obj.save(update_fields=["status"])
    return order


def _refresh_order_status(order):
    if order.is_fully_received:
        order.status = PurchaseOrder.RECEIVED
    elif any(line.quantity_received > 0 for line in order.lines.all()):
        order.status = PurchaseOrder.PARTIALLY_RECEIVED
    order.save(update_fields=["status"])


@transaction.atomic
def receive_goods(receipt, user=None):
    """For each GoodsReceiptLine on this receipt: increases the material's stock (via
    the same record_stock_movement used everywhere else in Inventory) and logs a
    matching inventory.Purchase row for cost/reporting traceability, then refreshes
    the parent PurchaseOrder's status from actual quantities received so far."""
    order = receipt.purchase_order
    for line in GoodsReceiptLine.objects.filter(receipt=receipt).select_related("order_line__material"):
        order_line = line.order_line
        if not line.quantity_received:
            continue
        Purchase.objects.create(
            material=order_line.material,
            supplier=order.supplier,
            quantity=line.quantity_received,
            unit_cost=order_line.unit_price,
            purchase_date=receipt.receipt_date,
            notes=f"Goods receipt {receipt.reference} for {order.reference}",
        )
        record_stock_movement(
            order_line.material,
            line.quantity_received,
            StockMovement.PURCHASE,
            reference=f"{receipt.reference} ({order.reference})",
            user=user,
        )

    _refresh_order_status(order)
    return order
