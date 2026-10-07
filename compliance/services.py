from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.urls import reverse

from employees.models import Employee

from .models import (
    Calibration, ComplianceDocument, Equipment, PersonnelDocument, PremisesRequirement, Procedure,
)

WARNING_DAYS = 30

VALID, EXPIRING, EXPIRED, NO_EXPIRY, MISSING = "valid", "expiring", "expired", "no_expiry", "missing"

# status -> (label, status_badge tone, sort priority — worst first)
STATUS_DISPLAY = {
    MISSING: ("Missing", "danger", 0),
    EXPIRED: ("Expired", "danger", 1),
    EXPIRING: ("Expiring soon", "warning", 2),
    VALID: ("Valid", "success", 3),
    NO_EXPIRY: ("No expiry", "neutral", 4),
}


def today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


def expiry_status(expiry_date, today_=None):
    today_ = today_ or today()
    if expiry_date is None:
        return NO_EXPIRY
    if expiry_date < today_:
        return EXPIRED
    if expiry_date <= today_ + timedelta(days=WARNING_DAYS):
        return EXPIRING
    return VALID


def is_current(status):
    """Usable as evidence right now: not expired and not absent. An expiring-soon
    document still counts — it's a renewal reminder, not a failure."""
    return status in (VALID, EXPIRING, NO_EXPIRY)


def food_handler_rows(today_=None):
    """Every active food handler with their newest medical certificate and its status,
    worst first. Judged on the newest certificate by expiry, so a renewed certificate
    supersedes an old expired one rather than leaving the employee flagged."""
    today_ = today_ or today()
    handlers = (
        Employee.objects.filter(is_food_handler=True, status=Employee.ACTIVE)
        .select_related("department").prefetch_related("medical_certificates")
    )
    rows = []
    for employee in handlers:
        cert = max(employee.medical_certificates.all(), key=lambda c: c.expiry_date, default=None)
        status = expiry_status(cert.expiry_date, today_) if cert else MISSING
        rows.append({"employee": employee, "certificate": cert, "status": status})
    rows.sort(key=lambda r: (STATUS_DISPLAY[r["status"]][2], r["employee"].first_name))
    return rows


def equipment_rows(today_=None):
    today_ = today_ or today()
    rows = []
    for equipment in Equipment.objects.filter(is_active=True).prefetch_related("calibrations"):
        latest = equipment.latest_calibration
        status = expiry_status(latest.next_due_date, today_) if latest else MISSING
        rows.append({"equipment": equipment, "calibration": latest, "status": status})
    rows.sort(key=lambda r: (STATUS_DISPLAY[r["status"]][2], r["equipment"].name))
    return rows


def best_document(category, today_=None):
    """(document, status) for the most useful document of `category`: the current one
    expiring last, else the newest expired one, else (None, MISSING)."""
    today_ = today_ or today()
    docs = [(d, expiry_status(d.expiry_date, today_)) for d in ComplianceDocument.objects.filter(category=category)]
    if not docs:
        return None, MISSING
    current = [pair for pair in docs if is_current(pair[1])]
    pool = current or docs
    return max(pool, key=lambda pair: pair[0].expiry_date or date.max)


_REQUIRED_PROCEDURES = [
    (Procedure.RECALL, "Product recall procedure"),
    (Procedure.COMPLAINT, "Customer complaint handling procedure"),
    (Procedure.PEST, "Pest control management"),
    (Procedure.WASTE, "Waste management procedure"),
    (Procedure.HYGIENE, "Cleaning, sanitation & hygiene schedule"),
    (Procedure.PERSONAL_HYGIENE, "Personal hygiene & protective clothing"),
    (Procedure.QC, "Quality control procedure"),
    (Procedure.CALIBRATION, "Equipment calibration procedure"),
]

_REQUIRED_DOCUMENTS = [
    (ComplianceDocument.PUBLIC_HEALTH, "Public Health Licence for the manufacturing premises"),
    (ComplianceDocument.BUSINESS_PERMIT, "Single Business Permit"),
    (ComplianceDocument.SCHEME, "Signed Scheme of Supervision and Control"),
    (ComplianceDocument.STD_EAS_38, "Copy of KS EAS 38:2014 (labelling)"),
    (ComplianceDocument.STD_EAS_153, "Copy of KS EAS 153:2018 (packaged drinking water)"),
    (ComplianceDocument.STD_EAS_459, "Copy of KS EAS 459 (code of hygiene)"),
]


def readiness_checklist(today_=None):
    """The KEBS application requirements, each ticked automatically from what's
    actually recorded in the system. `ok` is True/False, or None for a requirement the
    system can't evidence yet (shown as informational, never counted as failed)."""
    today_ = today_ or today()
    items = []
    documents_url = reverse("compliance:document_list")

    handlers = food_handler_rows(today_)
    ok_count = sum(1 for r in handlers if is_current(r["status"]))
    items.append({
        "label": "Valid medical certificate for every food handler",
        "ok": bool(handlers) and ok_count == len(handlers),
        "detail": f"{ok_count} of {len(handlers)} food handlers covered" if handlers else "No food handlers recorded",
        "url": reverse("compliance:medical_list"),
    })

    for category, label in _REQUIRED_DOCUMENTS:
        doc, status = best_document(category, today_)
        if doc is None:
            detail = "Not uploaded"
        elif status == EXPIRED:
            detail = f"Expired {doc.expiry_date:%d %b %Y}"
        elif status == EXPIRING:
            detail = f"Expires {doc.expiry_date:%d %b %Y} — renew soon"
        elif doc.expiry_date:
            detail = f"Valid until {doc.expiry_date:%d %b %Y}"
        else:
            detail = "On file"
        items.append({"label": label, "ok": is_current(status), "detail": detail, "url": documents_url})

    approved = {p.category for p in Procedure.objects.filter(status=Procedure.APPROVED)}
    existing = {p.category for p in Procedure.objects.all()}
    for category, label in _REQUIRED_PROCEDURES:
        if category in approved:
            detail = "Approved"
        elif category in existing:
            detail = "Written — awaiting approval"
        else:
            detail = "Not written"
        items.append({
            "label": label, "ok": category in approved, "detail": detail,
            "url": reverse("compliance:procedure_list"),
        })

    personnel = PersonnelDocument.objects.all()
    has_qualification = personnel.filter(doc_type=PersonnelDocument.QUALIFICATION).exists()
    has_employment = personnel.filter(doc_type=PersonnelDocument.EMPLOYMENT).exists()
    items.append({
        "label": "Quality control personnel: qualifications and evidence of employment",
        "ok": has_qualification and has_employment,
        "detail": (
            "On file" if has_qualification and has_employment
            else "Missing: " + " and ".join(
                part for part, present in (("qualifications", has_qualification), ("evidence of employment", has_employment))
                if not present
            )
        ),
        "url": reverse("compliance:personnel_list"),
    })

    equipment = equipment_rows(today_)
    current_equipment = sum(1 for r in equipment if is_current(r["status"]))
    items.append({
        "label": "Calibration certificates for critical measuring equipment",
        "ok": bool(equipment) and current_equipment == len(equipment),
        "detail": f"{current_equipment} of {len(equipment)} instruments calibrated" if equipment else "No equipment recorded",
        "url": reverse("compliance:equipment_list"),
    })

    items.append({
        "label": "Waste management, pest control and quality control records",
        "ok": None,
        "detail": "Day-to-day record keeping isn't tracked in the system yet — keep the paper records meanwhile",
        "url": None,
    })
    return items


def premises_progress():
    requirements = list(PremisesRequirement.objects.all())
    return requirements, sum(1 for r in requirements if r.is_met)


def compliance_alert_items(today_=None):
    """Bell-icon alerts: expired/expiring documents, certificates and calibrations,
    plus procedures awaiting approval or overdue for review."""
    today_ = today_ or today()
    alerts = []

    all_docs = list(ComplianceDocument.objects.all())
    for doc in all_docs:
        status = expiry_status(doc.expiry_date, today_)
        if status not in (EXPIRING, EXPIRED):
            continue
        superseded = doc.category != ComplianceDocument.OTHER and any(
            other.pk != doc.pk and other.category == doc.category
            and (other.expiry_date is None or other.expiry_date > doc.expiry_date)
            for other in all_docs
        )
        if superseded:
            continue
        verb = "expired on" if status == EXPIRED else "expires on"
        alerts.append({
            "message": f"{doc.title} {verb} {doc.expiry_date:%d %b %Y}",
            "url": reverse("compliance:document_list"),
            "tone": "danger" if status == EXPIRED else "warning",
        })

    missing_handlers = 0
    for row in food_handler_rows(today_):
        if row["status"] == MISSING:
            missing_handlers += 1
        elif row["status"] in (EXPIRING, EXPIRED):
            verb = "expired on" if row["status"] == EXPIRED else "expires on"
            alerts.append({
                "message": f"{row['employee'].get_full_name()}'s medical certificate {verb} {row['certificate'].expiry_date:%d %b %Y}",
                "url": reverse("compliance:medical_list"),
                "tone": "danger" if row["status"] == EXPIRED else "warning",
            })
    if missing_handlers:
        alerts.append({
            "message": f"{missing_handlers} food handler{'s' if missing_handlers != 1 else ''} without a medical certificate",
            "url": reverse("compliance:medical_list"),
            "tone": "danger",
        })

    for row in equipment_rows(today_):
        name = row["equipment"].name
        if row["status"] == MISSING:
            alerts.append({
                "message": f"{name} has no calibration certificate",
                "url": reverse("compliance:equipment_list"), "tone": "warning",
            })
        elif row["status"] in (EXPIRING, EXPIRED):
            verb = "calibration was due" if row["status"] == EXPIRED else "calibration is due"
            alerts.append({
                "message": f"{name} {verb} {row['calibration'].next_due_date:%d %b %Y}",
                "url": reverse("compliance:equipment_list"),
                "tone": "danger" if row["status"] == EXPIRED else "warning",
            })

    for procedure in Procedure.objects.filter(next_review_date__isnull=False, next_review_date__lt=today_):
        alerts.append({
            "message": f"{procedure.code} {procedure.title} is overdue for review",
            "url": reverse("compliance:procedure_detail", args=[procedure.pk]), "tone": "warning",
        })
    drafts = Procedure.objects.filter(status=Procedure.DRAFT).count()
    if drafts:
        alerts.append({
            "message": f"{drafts} procedure{'s' if drafts != 1 else ''} awaiting approval",
            "url": reverse("compliance:procedure_list"), "tone": "warning",
        })
    return alerts
