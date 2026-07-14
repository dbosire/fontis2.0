"""Production settings — points at the real live fontis_springs DB. Only used at cutover (Phase 9)."""

from .base import *  # noqa: F401,F403
from decouple import config

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME", default="fontis_springs"),
        "USER": config("DB_USER", default="root"),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default="127.0.0.1"),
        "PORT": config("DB_PORT", default="3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

# HTTPS is required once a reverse proxy terminating TLS sits in front of Waitress —
# Daraja mechanically requires an HTTPS callback URL for production, and the public
# M-Pesa payment page carries phone numbers over the wire. Off by default (matches
# today's behavior on the internal network); flip SECURE_SSL_REDIRECT=True in .env
# once that proxy exists. Standing up the proxy/TLS termination itself is
# infrastructure work outside this codebase.
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=False, cast=bool)
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in config("CSRF_TRUSTED_ORIGINS", default="").split(",") if origin.strip()
]
