from core.mixins import has_module_permission

from .services import compliance_alert_items


def compliance_alerts(request):
    """Merged into the topbar alert bell alongside inventory's. Only for users whose
    role can view Compliance — these alerts link into pages they'd otherwise be
    refused, and cost a handful of queries per page."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    if not has_module_permission(user, "compliance", "view"):
        return {"compliance_alerts": []}
    return {"compliance_alerts": compliance_alert_items()}
