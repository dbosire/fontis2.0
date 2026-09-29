def get_client_ip(request):
    """The originating client's IP, not the reverse proxy's own address. Production
    runs Waitress behind an nginx/IIS reverse proxy that terminates TLS (see the
    README's deploy section) — REMOTE_ADDR is that proxy's own loopback address for
    every request, so the real client only shows up in X-Forwarded-For, which the
    proxy sets. Falls back to REMOTE_ADDR for local dev, where there's no proxy."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
