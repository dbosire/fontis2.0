"""
Base Django settings for the fontis project, shared by local/production.
"""

from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="django-insecure-dev-key-override-in-env")

DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "tailwind",
    "theme",
    "django_htmx",
    "widget_tweaks",
    # project apps
    "core",
    "accounts",
    "maintenance",
    "sales",
    "debts",
    "contacts",
    "expenses",
    "mpesa",
    "water_test",
    "inventory",
    "employees",
    "crm",
    "finance",
    "purchasing",
    "commissions",
    "daily_reconciliation",
    "reports",
    "system_info",
    "ml_integration",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "accounts.middleware.MustChangePasswordMiddleware",
]

ROOT_URLCONF = "fontis.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
                "system_info.context_processors.site_settings",
                "inventory.context_processors.inventory_alerts",
            ],
        },
    },
]

WSGI_APPLICATION = "fontis.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
# The existing MySQL `datetime` columns hold naive local (Africa/Nairobi) wall-clock
# time written by the PHP app (which has no timezone awareness at all) — NOT UTC.
# USE_TZ=True would make Django wrongly assume those naive values are UTC and shift
# every date-based query/filter by the UTC+3 offset. Keeping USE_TZ=False treats them
# as literal local time, matching how the data was actually written.
USE_TZ = False

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "media/"
# Reuse the existing PHP app's uploads/ directory in place (same files referenced by
# system_info/users.avatar paths like "uploads/xxx.png") rather than duplicating assets.
MEDIA_ROOT = BASE_DIR.parent / "fontis"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "reports:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

TAILWIND_APP_NAME = "theme"
NPM_BIN_PATH = config("NPM_BIN_PATH", default=r"C:\Program Files\nodejs\npm.cmd")
INTERNAL_IPS = ["127.0.0.1"]

# ML microservice (existing FastAPI service in ../fontis/ml/, kept as-is)
ML_SERVICE_V1_URL = config("ML_SERVICE_V1_URL", default="http://127.0.0.1:8000")
ML_SERVICE_V2_URL = config("ML_SERVICE_V2_URL", default="http://127.0.0.1:8010")

# CRM: email. Defaults to printing to the console in dev; set EMAIL_HOST/etc. in .env
# (or EMAIL_BACKEND to django.core.mail.backends.smtp.EmailBackend) once a real SMTP
# account is available.
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="Fontis Springs <no-reply@fontissprings.co.ke>")
