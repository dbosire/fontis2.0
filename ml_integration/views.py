from django.conf import settings
from django.views.generic import TemplateView

from core.mixins import ModulePermissionRequiredMixin

from .services import MLClient, backtest_v1_model, compute_v1_predictions


class ViewMLIntegrationMixin(ModulePermissionRequiredMixin):
    module_name = "ml_integration"
    permission_level = "view"


class PredictorV1View(ViewMLIntegrationMixin, TemplateView):
    """Computed directly from Sale records in this app — see
    ml_integration/services.py::compute_v1_predictions(). No external service."""

    template_name = "ml_integration/predictions.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["version_label"] = "v1"
        ctx["predictions"] = compute_v1_predictions()
        ctx["model_score"] = backtest_v1_model()
        ctx["error"] = None
        return ctx


class PredictorV2View(ViewMLIntegrationMixin, TemplateView):
    """Still proxies the external FastAPI ML microservice at ML_SERVICE_V2_URL."""

    template_name = "ml_integration/predictions.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["version_label"] = "v2"
        try:
            ctx["predictions"] = MLClient(settings.ML_SERVICE_V2_URL).predict_all()
            ctx["error"] = None
        except Exception as exc:
            ctx["predictions"] = []
            ctx["error"] = str(exc)
        return ctx
