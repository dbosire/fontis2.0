from django.conf import settings
from django.core.paginator import Paginator
from django.views.generic import TemplateView

from core.mixins import ModulePermissionRequiredMixin

from .services import MLClient, backtest_v1_model, compute_v1_predictions

PAGE_SIZE = 30


class ViewMLIntegrationMixin(ModulePermissionRequiredMixin):
    module_name = "ml_integration"
    permission_level = "view"


def _paginate(request, items):
    page_obj = Paginator(items, PAGE_SIZE).get_page(request.GET.get("page"))
    return page_obj, page_obj.has_other_pages()


class PredictorV1View(ViewMLIntegrationMixin, TemplateView):
    """Computed directly from Sale records in this app — see
    ml_integration/services.py::compute_v1_predictions(). No external service."""

    template_name = "ml_integration/predictions.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["version_label"] = "v1"
        ctx["has_category"] = True
        ctx["model_score"] = backtest_v1_model()
        ctx["predictions"], ctx["is_paginated"] = _paginate(self.request, compute_v1_predictions())
        ctx["page_obj"] = ctx["predictions"]
        ctx["error"] = None
        return ctx


class PredictorV2View(ViewMLIntegrationMixin, TemplateView):
    """Still proxies the external FastAPI ML microservice at ML_SERVICE_V2_URL —
    its response has no category field of its own, so the table's Category column
    only appears on v1."""

    template_name = "ml_integration/predictions.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["version_label"] = "v2"
        ctx["has_category"] = False
        try:
            all_predictions = MLClient(settings.ML_SERVICE_V2_URL).predict_all()
            ctx["predictions"], ctx["is_paginated"] = _paginate(self.request, all_predictions)
            ctx["page_obj"] = ctx["predictions"]
            ctx["error"] = None
        except Exception as exc:
            ctx["predictions"] = []
            ctx["is_paginated"] = False
            ctx["error"] = str(exc)
        return ctx
