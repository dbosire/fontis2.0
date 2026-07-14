from django.db import transaction
from django.db.models import F

from .models import RawMaterial, StockMovement


def record_stock_movement(material, quantity_delta, movement_type, reference="", user=None):
    """Apply a signed quantity_delta to material.current_stock and log a StockMovement.
    Positive = stock in, negative = stock out. No-op if delta is 0 so unrelated saves
    (e.g. editing a sale's customer name) never create a phantom zero-quantity entry."""
    if not quantity_delta:
        return None
    with transaction.atomic():
        RawMaterial.objects.filter(pk=material.pk).update(current_stock=F("current_stock") + quantity_delta)
        material.refresh_from_db(fields=["current_stock"])
        return StockMovement.objects.create(
            material=material,
            movement_type=movement_type,
            quantity=quantity_delta,
            reference=reference,
            created_by=user,
        )


def _consume_for_jar_type(jar_type, quantity_sold_delta, sale, user):
    """quantity_sold_delta > 0 means MORE of this product was sold (every material it
    consumes should go DOWN); quantity_sold_delta < 0 means LESS was sold, i.e. a
    restock (stock goes UP). A single product can consume several materials at once
    (e.g. a bottle + a cap + a label per sale), so this applies a movement for each."""
    if not quantity_sold_delta:
        return
    for usage in jar_type.material_usages.select_related("material").all():
        material_delta = -quantity_sold_delta * usage.quantity_per_sale
        record_stock_movement(
            usage.material,
            material_delta,
            StockMovement.SALE,
            reference=f"Sale #{sale.pk} - {jar_type.name}",
            user=user,
        )


def apply_sale_item_stock_deltas(old_items, new_items, sale, user=None):
    """Diff the sale's line items before/after a save and apply the resulting inventory
    movement per affected product's linked raw material — so editing a sale (changing a
    quantity, swapping a product, or removing a line) adjusts stock by the delta only,
    rather than re-consuming the full amount on every save.

    old_items / new_items: {sale_item_pk: (jar_type, quantity)}
    """
    for pk in set(old_items) | set(new_items):
        old = old_items.get(pk)
        new = new_items.get(pk)

        if old and new:
            old_jar_type, old_qty = old
            new_jar_type, new_qty = new
            if old_jar_type.pk != new_jar_type.pk:
                _consume_for_jar_type(old_jar_type, -old_qty, sale, user)
                _consume_for_jar_type(new_jar_type, new_qty, sale, user)
            elif old_qty != new_qty:
                _consume_for_jar_type(new_jar_type, new_qty - old_qty, sale, user)
        elif new and not old:
            new_jar_type, new_qty = new
            _consume_for_jar_type(new_jar_type, new_qty, sale, user)
        elif old and not new:
            old_jar_type, old_qty = old
            _consume_for_jar_type(old_jar_type, -old_qty, sale, user)


def restock_for_deleted_sale(sale, user=None):
    """Reverse the stock consumption for every line item of a sale that's about to be
    deleted. Must be called BEFORE the sale (and its cascade-deleted items) are removed."""
    for item in sale.items.select_related("jar_type").all():
        _consume_for_jar_type(item.jar_type, -item.quantity, sale, user)
