from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class MustChangePasswordMiddleware:
    """Forces users flagged must_change_password to the password-change form before anything else.

    Note: request.resolver_match is not populated yet during the request phase of
    middleware (it's only set once the handler resolves the view), so exemptions here
    must be checked against request.path directly rather than resolver_match/url names.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._exempt_paths = None

    def _get_exempt_paths(self):
        if self._exempt_paths is None:
            self._exempt_paths = {reverse("accounts:change_password"), reverse("accounts:logout")}
        return self._exempt_paths

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user
            and user.is_authenticated
            and getattr(user, "must_change_password", False)
            and request.path not in self._get_exempt_paths()
            and not request.path.lstrip("/").startswith(settings.STATIC_URL)
            and not request.path.lstrip("/").startswith(settings.MEDIA_URL)
        ):
            return redirect(reverse("accounts:change_password"))
        return self.get_response(request)
