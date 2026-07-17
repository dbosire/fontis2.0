from contacts.models import Contact
from crm.models import CustomerLoyalty, LoyaltyProgram, LoyaltyTransaction


def award_points_for_sale(sale, user=None):
    """Auto-earn loyalty points for a paid sale whose customer_name matches an existing
    Contact. Guest sales and unmatched names are skipped — loyalty needs a real customer
    record to track a balance against. Idempotent: keyed on a "sale:<id>" reference, so
    re-saving an already-paid sale (e.g. editing quantities) never double-awards.
    """
    from sales.models import Sale

    if sale.status not in (Sale.CASH, Sale.MPESA, Sale.CREDIT):
        return None
    if not sale.customer_name or sale.customer_name.strip().lower() == "guest":
        return None

    reference = f"sale:{sale.pk}"
    contact = Contact.objects.filter(name__iexact=sale.customer_name.strip()).first()
    if not contact:
        return None

    if LoyaltyTransaction.objects.filter(reference=reference, transaction_type=LoyaltyTransaction.EARN).exists():
        return None

    program = LoyaltyProgram.get_solo()
    if program.points_per_amount <= 0:
        return None

    points = sale.amount / program.points_per_amount
    if points <= 0:
        return None

    loyalty, _ = CustomerLoyalty.objects.get_or_create(contact=contact)
    loyalty.points_balance += points
    loyalty.save(update_fields=["points_balance"])

    return LoyaltyTransaction.objects.create(
        customer_loyalty=loyalty,
        points=points,
        transaction_type=LoyaltyTransaction.EARN,
        reference=reference,
        note=f"Earned from sale #{sale.pk}",
        created_by=user if user and user.is_authenticated else None,
    )


def adjust_points(customer_loyalty, points, transaction_type, note="", user=None):
    """Manually earn/redeem/adjust points for a customer. `points` should already carry
    the correct sign (negative for redemptions/downward adjustments)."""
    customer_loyalty.points_balance += points
    customer_loyalty.save(update_fields=["points_balance"])
    return LoyaltyTransaction.objects.create(
        customer_loyalty=customer_loyalty,
        points=points,
        transaction_type=transaction_type,
        note=note,
        created_by=user if user and user.is_authenticated else None,
    )
