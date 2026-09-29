from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import ActivityLog
from .utils import get_client_ip


def _client_ip(request):
    return get_client_ip(request) if request else None


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    ActivityLog.objects.create(
        user=user,
        username=user.get_username(),
        event_type=ActivityLog.LOGIN,
        ip_address=_client_ip(request),
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    # user is None if the session had already expired/logged out by the time this fires.
    ActivityLog.objects.create(
        user=user,
        username=user.get_username() if user else "",
        event_type=ActivityLog.LOGOUT,
        ip_address=_client_ip(request),
    )


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request=None, **kwargs):
    ActivityLog.objects.create(
        user=None,
        username=credentials.get("username", "")[:255],
        event_type=ActivityLog.LOGIN_FAILED,
        ip_address=_client_ip(request),
    )
