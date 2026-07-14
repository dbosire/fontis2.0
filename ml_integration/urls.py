from django.urls import path

from . import views

app_name = "ml_integration"

urlpatterns = [
    path("v1/", views.PredictorV1View.as_view(), name="predictor_v1"),
    path("v2/", views.PredictorV2View.as_view(), name="predictor_v2"),
]
