from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    # Public, unauthenticated payment pages + Daraja webhooks — deliberately outside
    # every other prefix below, none of which are permission-gated by design.
    path("pay/", include("mpesa.public_urls")),
    path("accounts/", include("accounts.urls")),
    path("", include("reports.urls")),
    path("sales/", include("sales.urls")),
    path("maintenance/", include("maintenance.urls")),
    path("contacts/", include("contacts.urls")),
    path("debts/", include("debts.urls")),
    path("expenses/", include("expenses.urls")),
    path("mpesa/", include("mpesa.urls")),
    path("water-test/", include("water_test.urls")),
    path("inventory/", include("inventory.urls")),
    path("employees/", include("employees.urls")),
    path("crm/", include("crm.urls")),
    path("finance/", include("finance.urls")),
    path("purchasing/", include("purchasing.urls")),
    path("commissions/", include("commissions.urls")),
    path("reconciliation/", include("daily_reconciliation.urls")),
    path("system-info/", include("system_info.urls")),
    path("ml/", include("ml_integration.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
