from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class ComingSoonView(LoginRequiredMixin, TemplateView):
    """Placeholder for modules not yet built out in the rewrite (tracked in Phase 4).
    Pass extra_context={"page_title": "..."} via .as_view() at the URL conf level."""

    template_name = "core/coming_soon.html"
    extra_context = {"page_title": "Coming soon"}
