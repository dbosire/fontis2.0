import httpx
from decouple import config

from crm.models import SmsMessage

SMS_API_URL = config("SMS_API_URL", default="https://sms.sourcecode.co.ke/api/v3/sms/send")
SMS_API_TOKEN = config("SMS_API_TOKEN", default="")
SMS_SENDER_ID = config("SMS_SENDER_ID", default="FontisSprings")


def send_sms(recipient, message, sender_id=None, msg_type="plain", contact=None, promotion=None, user=None):
    """Send an SMS via the SourceCode API and log the attempt as an SmsMessage row.

    Always returns the SmsMessage log row, never raises — a provider/network failure is
    recorded as a FAILED log entry rather than blocking the caller (bulk sends need to
    keep going through a recipient list even if one number fails).
    """
    log = SmsMessage.objects.create(
        contact=contact,
        promotion=promotion,
        recipient=recipient,
        sender_id=sender_id or SMS_SENDER_ID,
        message=message,
        status=SmsMessage.PENDING,
        sent_by=user if user and user.is_authenticated else None,
    )

    if not SMS_API_TOKEN:
        log.status = SmsMessage.FAILED
        log.provider_response = "SMS_API_TOKEN is not configured (.env)."
        log.save(update_fields=["status", "provider_response"])
        return log

    try:
        response = httpx.post(
            SMS_API_URL,
            headers={
                "Authorization": f"Bearer {SMS_API_TOKEN}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "recipient": recipient,
                "sender_id": sender_id or SMS_SENDER_ID,
                "type": msg_type,
                "message": message,
            },
            timeout=15,
        )
        log.provider_response = response.text[:2000]
        log.status = SmsMessage.SENT if response.status_code < 300 else SmsMessage.FAILED
    except httpx.HTTPError as exc:
        log.status = SmsMessage.FAILED
        log.provider_response = str(exc)[:2000]

    log.save(update_fields=["status", "provider_response"])
    return log
