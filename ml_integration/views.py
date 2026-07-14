from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from .services import MLClient


class BasePredictorView(LoginRequiredMixin, TemplateView):
    template_name = "ml_integration/predictions.html"
    service_url_setting = None
    version_label = ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["version_label"] = self.version_label
        base_url = getattr(settings, self.service_url_setting)
        try:
            ctx["predictions"] = MLClient(base_url).predict_all()
            ctx["error"] = None
        except Exception as exc:
            ctx["predictions"] = []
            ctx["error"] = str(exc)
        return ctx


class PredictorV1View(BasePredictorView):
    service_url_setting = "ML_SERVICE_V1_URL"
    version_label = "v1"


class PredictorV2View(BasePredictorView):
    service_url_setting = "ML_SERVICE_V2_URL"
    version_label = "v2"
