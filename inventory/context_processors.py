from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import F
from django.urls import reverse

from .models import Purchase, RawMaterial


def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


def inventory_alerts(request):
    """Low-stock materials and expiring/expired purchase batches, surfaced globally
    via the topbar alert bell. Only computed for logged-in requests since the alerts
    link to admin-only pages and there's no point querying for anonymous visitors."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    today = _today()
    soon_cutoff = today + timedelta(days=30)

    alerts = []

    low_stock = RawMaterial.objects.filter(current_stock__lte=F("reorder_level")).order_by("name")
    for material in low_stock:
        alerts.append(
            {
                "message": f"{material.name} is low on stock ({material.current_stock:g} {material.unit} left)",
                "url": reverse("inventory:reorder_levels"),
                "tone": "warning",
            }
        )

    expiring = (
        Purchase.objects.select_related("material")
        .filter(expiry_date__isnull=False, expiry_date__lte=soon_cutoff)
        .order_by("expiry_date")
    )
    for purchase in expiring:
        if purchase.expiry_date < today:
            message = f"{purchase.material.name} batch expired on {purchase.expiry_date:%d %b %Y}"
            tone = "danger"
        else:
            message = f"{purchase.material.name} batch expires on {purchase.expiry_date:%d %b %Y}"
            tone = "warning"
        alerts.append({"message": message, "url": reverse("inventory:expiry_dates"), "tone": tone})

    return {"inventory_alerts": alerts}
