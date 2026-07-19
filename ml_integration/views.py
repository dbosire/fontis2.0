from django.conf import settings
from django.core.paginator import Paginator
from django.views.generic import TemplateView

from core.mixins import ModulePermissionRequiredMixin

from .services import MLClient, backtest_v1_model, compute_v1_predictions

PAGE_SIZE = 30
CATEGORY_CHOICES = ["Upcoming", "Due Now", "Overdue", "Churned"]


class ViewMLIntegrationMixin(ModulePermissionRequiredMixin):
    module_name = "ml_integration"
    permission_level = "view"


def _paginate(request, items):
    page_obj = Paginator(items, PAGE_SIZE).get_page(request.GET.get("page"))
    return page_obj, page_obj.has_other_pages()


class BasePredictorView(ViewMLIntegrationMixin, TemplateView):
    template_name = "ml_integration/predictions.html"
    version_label = ""
    has_category = False
    list_url_name = ""

    def get_template_names(self):
        # Search-as-you-type: an htmx request only needs the results partial (table
        # + pagination), not the full page with the search form and sidebar — same
        # pattern as sales/views.py::SaleListView.
        if self.request.htmx:
            return ["ml_integration/prediction_results.html"]
        return [self.template_name]

    def get_all_predictions(self):
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["version_label"] = self.version_label
        ctx["has_category"] = self.has_category
        ctx["category_choices"] = CATEGORY_CHOICES
        ctx["list_url_name"] = self.list_url_name

        q = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category", "").strip()
        ctx["filters"] = {"q": q, "category": category}

        try:
            predictions = self.get_all_predictions()
            ctx["error"] = None
        except Exception as exc:
            predictions = []
            ctx["error"] = str(exc)

        if q:
            predictions = [p for p in predictions if q.lower() in str(p.get("customer_name", "")).lower()]
        if category:
            predictions = [p for p in predictions if p.get("category") == category]

        ctx["predictions"], ctx["is_paginated"] = _paginate(self.request, predictions)
        ctx["page_obj"] = ctx["predictions"]

        # preserve the active filters on pagination links without the page param
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class PredictorV1View(BasePredictorView):
    """Computed directly from Sale records in this app — see
    ml_integration/services.py::compute_v1_predictions(). No external service."""

    version_label = "v1"
    has_category = True
    list_url_name = "ml_integration:predictor_v1"

    def get_all_predictions(self):
        return compute_v1_predictions()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model_score"] = backtest_v1_model()
        return ctx


class PredictorV2View(BasePredictorView):
    """Still proxies the external FastAPI ML microservice at ML_SERVICE_V2_URL —
    its response has no category field of its own, so the Category filter/column
    only appears on v1."""

    version_label = "v2"
    has_category = False
    list_url_name = "ml_integration:predictor_v2"

    def get_all_predictions(self):
        return MLClient(settings.ML_SERVICE_V2_URL).predict_all()
