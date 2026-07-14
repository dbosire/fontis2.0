from django.core.mail import send_mail
from django.conf import settings

from crm.models import EmailLog


def send_customer_email(recipient, subject, body, contact=None, promotion=None, user=None):
    """Send an email via Django's configured EMAIL_BACKEND and log the attempt as an
    EmailLog row. Always returns the log row rather than raising, matching send_sms()."""
    log = EmailLog.objects.create(
        contact=contact,
        promotion=promotion,
        recipient=recipient,
        subject=subject,
        body=body,
        status=EmailLog.PENDING,
        sent_by=user if user and user.is_authenticated else None,
    )

    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
        log.status = EmailLog.SENT
    except Exception as exc:
        log.status = EmailLog.FAILED
        log.error_message = str(exc)[:2000]

    log.save(update_fields=["status", "error_message"])
    return log
