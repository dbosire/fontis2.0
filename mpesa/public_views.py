import json
import logging

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import PaymentLink, STKPushAttempt
from .services.daraja import DarajaError, MPESA_TILL_NUMBER, initiate_stk_push, normalize_phone_number
from .services.reconciliation import handle_c2b_confirmation, handle_stk_callback

logger = logging.getLogger(__name__)

STK_TOKEN_LIMIT, STK_TOKEN_WINDOW = 3, 600
STK_IP_LIMIT, STK_IP_WINDOW = 10, 600
POLL_IP_LIMIT, POLL_IP_WINDOW = 60, 600


def _client_ip(request):
    # No reverse proxy in front of this app today — see fontis/settings/production.py.
    # If one is added later, this must switch to a trusted X-Forwarded-For parse.
    return request.META.get("REMOTE_ADDR", "unknown")


def _rate_limited(key, limit, window_seconds):
    cache.get_or_set(key, 0, timeout=window_seconds)
    count = cache.incr(key)
    return count > limit


def _get_link_or_none(token):
    return PaymentLink.objects.filter(token=token).prefetch_related("sales").first()


class PayView(View):
    template_name = "mpesa/pay.html"

    def get(self, request, token):
        link = _get_link_or_none(token)
        if link is None:
            return render(request, self.template_name, {"invalid": True})
        if link.status == PaymentLink.PAID:
            return render(request, self.template_name, {"link": link, "paid": True})
        if link.status in (PaymentLink.CANCELLED, PaymentLink.EXPIRED) or link.is_expired:
            return render(request, self.template_name, {"invalid": True})
        return render(request, self.template_name, {
            "link": link, "phone_prefill": link.phone_number, "mpesa_till_number": MPESA_TILL_NUMBER,
        })


class TriggerSTKPushView(View):
    def post(self, request, token):
        link = _get_link_or_none(token)
        if link is None or link.status != PaymentLink.PENDING or link.is_expired:
            return JsonResponse({"ok": False, "error": "This payment link is no longer valid."}, status=400)

        if _rate_limited(f"mpesa:stk_rl:token:{token}", STK_TOKEN_LIMIT, STK_TOKEN_WINDOW) or _rate_limited(
            f"mpesa:stk_rl:ip:{_client_ip(request)}", STK_IP_LIMIT, STK_IP_WINDOW
        ):
            return JsonResponse({"ok": False, "error": "Too many attempts — please try again in a few minutes."}, status=429)

        phone = normalize_phone_number(request.POST.get("phone_number", ""))
        if not phone:
            return JsonResponse({"ok": False, "error": "Enter a valid phone number, e.g. 0712345678."}, status=400)

        try:
            merchant_request_id, checkout_request_id = initiate_stk_push(
                phone, link.amount, account_reference=f"INV{link.pk}", description="Fontis Springs payment",
            )
        except DarajaError as exc:
            logger.error("mpesa: STK push failed for link %s: %s", link.token, exc)
            return JsonResponse({"ok": False, "error": "Could not start the M-Pesa prompt. Please try again shortly."}, status=502)

        STKPushAttempt.objects.create(
            payment_link=link, phone_number=phone, amount=link.amount,
            merchant_request_id=merchant_request_id, checkout_request_id=checkout_request_id,
        )
        return JsonResponse({"ok": True})


class PaymentStatusPollView(View):
    def get(self, request, token):
        if _rate_limited(f"mpesa:poll_rl:ip:{_client_ip(request)}", POLL_IP_LIMIT, POLL_IP_WINDOW):
            return JsonResponse({"status": "unknown"}, status=429)

        link = _get_link_or_none(token)
        if link is None:
            return JsonResponse({"status": "unknown"}, status=404)
        if link.status == PaymentLink.PAID:
            return JsonResponse({"status": "paid"})
        latest_attempt = link.stk_attempts.order_by("-date_created").first()
        if latest_attempt and latest_attempt.status in (STKPushAttempt.FAILED, STKPushAttempt.CANCELLED, STKPushAttempt.TIMEOUT):
            return JsonResponse({"status": "failed"})
        return JsonResponse({"status": "pending"})


@method_decorator(csrf_exempt, name="dispatch")
class STKCallbackView(View):
    def post(self, request):
        try:
            payload = json.loads(request.body)
        except (ValueError, TypeError):
            logger.error("mpesa: unparseable STK callback body: %r", request.body[:2000])
            payload = None
        if payload is not None:
            try:
                handle_stk_callback(payload)
            except Exception:
                logger.exception("mpesa: error handling STK callback")
        # Always ack — Daraja retries aggressively on anything else.
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@method_decorator(csrf_exempt, name="dispatch")
class C2BValidationView(View):
    def post(self, request):
        # Till payments should never be blocked at the point of sale.
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@method_decorator(csrf_exempt, name="dispatch")
class C2BConfirmationView(View):
    def post(self, request):
        try:
            payload = json.loads(request.body)
        except (ValueError, TypeError):
            logger.error("mpesa: unparseable C2B confirmation body: %r", request.body[:2000])
            payload = None
        if payload is not None:
            try:
                handle_c2b_confirmation(payload)
            except Exception:
                logger.exception("mpesa: error handling C2B confirmation")
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
