import shutil
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import connection

from crm.models import EmailLog, SmsMessage
from crm.services.sms import SMS_API_TOKEN
from mpesa.models import MpesaC2BTransaction, STKPushAttempt, WebhookErrorLog
from mpesa.services.daraja import is_configured as mpesa_is_configured

from .models import ScheduledTaskRun

BACKUP_DIR = settings.BASE_DIR / "backups"


def _now():
    # USE_TZ=False project-wide — naive local time only, matching every other app.
    return datetime.now(ZoneInfo("Africa/Nairobi")).replace(tzinfo=None)


def _check(ok, detail):
    return {"ok": ok, "detail": detail}


def database_check():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
        return _check(True, f"{connection.vendor} {version}")
    except Exception as exc:
        return _check(False, str(exc)[:200])


def scheduler_check():
    """The most recent cron-triggered backup_db run — a manual "Back up now" click
    doesn't count here, so a stalled cron job can't hide behind a staff member
    clicking the button (see ScheduledTaskRun's docstring)."""
    last = ScheduledTaskRun.objects.filter(task="backup", source=ScheduledTaskRun.CRON).first()
    if last is None:
        return _check(False, "No cron run recorded yet")
    return _check(last.status == ScheduledTaskRun.OK, f"Last run {last.started_at:%d %b %Y %H:%M}")


def backup_check():
    """Latest backup FILE regardless of who triggered it — distinct from
    scheduler_check(), which only cares about cron. A same-day manual backup still
    counts as "we have a recent backup", even if the cron job itself is stalled."""
    if not BACKUP_DIR.exists():
        return _check(False, "No backups yet")
    files = sorted(BACKUP_DIR.glob("fontis-*.sql.gz"))
    if not files:
        return _check(False, "No backups yet")
    mtime = datetime.fromtimestamp(files[-1].stat().st_mtime)
    return _check(True, f"Last backup {mtime:%d %b %Y %H:%M}")


def mpesa_configured_check():
    ok = mpesa_is_configured()
    return _check(ok, "Configured" if ok else "No active configuration")


def last_mpesa_callback_check():
    """Latest genuine webhook receipt — a C2B confirmation's own date_created, or an
    STKPushAttempt's date_updated once it's moved out of REQUESTED (that status
    means only "push sent", not "callback received" — see STKPushAttempt.STATUS_CHOICES)."""
    c2b_latest = MpesaC2BTransaction.objects.order_by("-date_created").values_list("date_created", flat=True).first()
    stk_latest = (
        STKPushAttempt.objects.exclude(status=STKPushAttempt.REQUESTED)
        .order_by("-date_updated").values_list("date_updated", flat=True).first()
    )
    candidates = [t for t in (c2b_latest, stk_latest) if t is not None]
    if not candidates:
        return _check(False, "None received")
    return _check(True, f"{max(candidates):%d %b %Y %H:%M}")


def sms_gateway_check():
    ok = bool(SMS_API_TOKEN)
    return _check(ok, "Configured" if ok else "Not configured — set SMS_API_TOKEN in .env")


def email_check():
    if "console" in settings.EMAIL_BACKEND.lower():
        return _check(False, "Console / log only (dev)")
    return _check(bool(settings.EMAIL_HOST), settings.EMAIL_HOST or "Not configured")


def https_check():
    ok = getattr(settings, "SECURE_SSL_REDIRECT", False)
    return _check(ok, "Enforced" if ok else "Set SECURE_SSL_REDIRECT=True in production")


def debug_check():
    ok = not settings.DEBUG
    return _check(ok, "DEBUG=False in production" if ok else "DEBUG is on")


def all_checks():
    return {
        "Database": database_check(),
        "Daily scheduler": scheduler_check(),
        "Database backup": backup_check(),
        "M-Pesa configured": mpesa_configured_check(),
        "Last M-Pesa callback": last_mpesa_callback_check(),
        "SMS gateway": sms_gateway_check(),
        "Email": email_check(),
        "HTTPS enforced": https_check(),
        "Debug mode off": debug_check(),
    }


def operations():
    cutoff = _now() - timedelta(hours=24)
    failed_messages = (
        SmsMessage.objects.filter(status=SmsMessage.FAILED, date_created__gte=cutoff).count()
        + EmailLog.objects.filter(status=EmailLog.FAILED, date_created__gte=cutoff).count()
    )
    pending_stk = STKPushAttempt.objects.filter(status=STKPushAttempt.REQUESTED).count()
    unmatched_mpesa = MpesaC2BTransaction.objects.filter(status=MpesaC2BTransaction.UNMATCHED).count()
    rejected_callbacks = WebhookErrorLog.objects.filter(date_created__gte=cutoff).count()
    return {
        "Failed messages (24h)": failed_messages,
        "Pending STK pushes": pending_stk,
        "Unmatched M-Pesa": unmatched_mpesa,
        "Rejected callbacks (24h)": rejected_callbacks,
    }


def disk_usage():
    total, used, free = shutil.disk_usage(settings.BASE_DIR)
    gb = 1024 ** 3
    return {
        "free_gb": round(free / gb, 1), "total_gb": round(total / gb, 1),
        "used_pct": round(used / total * 100, 1) if total else 0,
    }


def scheduler_runs(limit=10):
    return list(ScheduledTaskRun.objects.filter(source=ScheduledTaskRun.CRON)[:limit])


def list_backups(limit=20):
    if not BACKUP_DIR.exists():
        return []
    files = sorted(BACKUP_DIR.glob("fontis-*.sql.gz"), key=lambda p: p.name, reverse=True)
    return [
        {"name": p.name, "size": p.stat().st_size, "mtime": datetime.fromtimestamp(p.stat().st_mtime)}
        for p in files[:limit]
    ]
