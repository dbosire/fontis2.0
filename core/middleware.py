from .models import ActivityLog

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Login/logout are handled with more detail by core/signals.py (which knows *why* an
# auth attempt failed); logging them again here as generic "action" rows would just
# duplicate those entries.
EXCLUDED_PATH_PREFIXES = ("/accounts/login/", "/accounts/logout/")


class ActivityLogMiddleware:
    """Logs every successful state-changing request (POST/PUT/PATCH/DELETE that
    didn't 4xx/5xx) as an ActivityLog row — gives audit coverage of every mutation
    in the app without instrumenting each of the ~200 view classes individually."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._log(request, response)
        return response

    def _log(self, request, response):
        if request.method not in MUTATING_METHODS:
            return
        if request.path.startswith(EXCLUDED_PATH_PREFIXES):
            return
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return
        if response.status_code >= 400:
            return
        match = getattr(request, "resolver_match", None)
        ActivityLog.objects.create(
            user=user,
            username=user.get_username(),
            event_type=ActivityLog.ACTION,
            method=request.method,
            path=request.path[:500],
            module=(match.app_name if match else "") or "",
            view_name=(match.view_name if match else "") or "",
            status_code=response.status_code,
            ip_address=request.META.get("REMOTE_ADDR"),
        )
