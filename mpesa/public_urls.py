from django.urls import path

from . import public_views as views

app_name = "mpesa_public"

urlpatterns = [
    path("callback/stk/", views.STKCallbackView.as_view(), name="stk_callback"),
    path("callback/c2b/validation/", views.C2BValidationView.as_view(), name="c2b_validation"),
    path("callback/c2b/confirmation/", views.C2BConfirmationView.as_view(), name="c2b_confirmation"),
    path("<str:token>/", views.PayView.as_view(), name="pay"),
    path("<str:token>/stk/", views.TriggerSTKPushView.as_view(), name="trigger_stk"),
    path("<str:token>/status/", views.PaymentStatusPollView.as_view(), name="status"),
]
