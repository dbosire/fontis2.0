import base64
import re
from datetime import datetime

import httpx
from decouple import config
from django.core.cache import cache

MPESA_ENV = config("MPESA_ENV", default="sandbox")
MPESA_BASE_URL = (
    "https://api.safaricom.co.ke" if MPESA_ENV == "production" else "https://sandbox.safaricom.co.ke"
)
MPESA_CONSUMER_KEY = config("MPESA_CONSUMER_KEY", default="")
MPESA_CONSUMER_SECRET = config("MPESA_CONSUMER_SECRET", default="")
MPESA_SHORTCODE = config("MPESA_SHORTCODE", default="")
MPESA_PASSKEY = config("MPESA_PASSKEY", default="")
MPESA_CALLBACK_BASE_URL = config("MPESA_CALLBACK_BASE_URL", default="")

_TOKEN_CACHE_KEY = "mpesa_daraja_access_token"


class DarajaError(Exception):
    pass


def is_configured():
    return bool(MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET and MPESA_SHORTCODE and MPESA_PASSKEY)


def normalize_phone_number(raw):
    """Normalize 07XXXXXXXX / +254XXXXXXXXX / 254XXXXXXXXX to Daraja's expected
    2547XXXXXXXX / 2541XXXXXXXX form. Returns None if it doesn't look like a valid
    Kenyan mobile number, so callers can reject bad input before hitting the API."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif digits.startswith("254") and len(digits) == 12:
        pass
    elif digits.startswith("7") or digits.startswith("1"):
        if len(digits) == 9:
            digits = "254" + digits
    if len(digits) != 12 or not digits.startswith("254"):
        return None
    return digits


def get_access_token():
    token = cache.get(_TOKEN_CACHE_KEY)
    if token:
        return token

    credentials = base64.b64encode(f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}".encode()).decode()
    response = httpx.get(
        f"{MPESA_BASE_URL}/oauth/v1/generate",
        params={"grant_type": "client_credentials"},
        headers={"Authorization": f"Basic {credentials}"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    token = data["access_token"]
    # Daraja tokens last 3600s — cache for slightly less so we never use a stale one.
    cache.set(_TOKEN_CACHE_KEY, token, timeout=3540)
    return token


def _stk_password(timestamp):
    raw = f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}"
    return base64.b64encode(raw.encode()).decode()


def initiate_stk_push(phone_number, amount, account_reference, description="Payment"):
    """phone_number must already be normalized (2547XXXXXXXX). Returns
    (merchant_request_id, checkout_request_id) on success. Raises DarajaError on any
    failure — callers are responsible for surfacing a friendly message and NOT leaking
    the raw exception text to the anonymous public page."""
    if not is_configured():
        raise DarajaError("M-Pesa is not configured (.env) — set MPESA_CONSUMER_KEY etc.")
    if not MPESA_CALLBACK_BASE_URL:
        raise DarajaError("MPESA_CALLBACK_BASE_URL is not configured (.env).")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    token = get_access_token()

    response = httpx.post(
        f"{MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": _stk_password(timestamp),
            "Timestamp": timestamp,
            "TransactionType": "CustomerBuyGoodsOnline",
            "Amount": int(round(amount)),
            "PartyA": phone_number,
            "PartyB": MPESA_SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": f"{MPESA_CALLBACK_BASE_URL}/pay/callback/stk/",
            "AccountReference": account_reference[:12],
            "TransactionDesc": description[:100],
        },
        timeout=30,
    )
    data = response.json()
    if response.status_code >= 300 or "CheckoutRequestID" not in data:
        raise DarajaError(data.get("errorMessage") or data.get("ResponseDescription") or "STK push request failed.")
    return data["MerchantRequestID"], data["CheckoutRequestID"]
