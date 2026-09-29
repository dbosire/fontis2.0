from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, TemplateView

from .mixins import SuperuserRequiredMixin
from .models import ActivityLog


class ComingSoonView(LoginRequiredMixin, TemplateView):
    """Placeholder for modules not yet built out in the rewrite (tracked in Phase 4).
    Pass extra_context={"page_title": "..."} via .as_view() at the URL conf level."""

    template_name = "core/coming_soon.html"
    extra_context = {"page_title": "Coming soon"}


class ActivityLogListView(SuperuserRequiredMixin, ListView):
    """Superuser-only, like System Health and Users: this is oversight tooling over
    every other user's actions, not something a Role's "edit" on some module should
    grant access to."""

    model = ActivityLog
    template_name = "core/activity_log_list.html"
    context_object_name = "logs"
    paginate_by = 50

    def get_queryset(self):
        qs = ActivityLog.objects.select_related("user")
        params = self.request.GET
        username = params.get("username", "").strip()
        if username:
            qs = qs.filter(username__icontains=username)
        event_type = params.get("event_type", "")
        if event_type:
            qs = qs.filter(event_type=event_type)
        module = params.get("module", "")
        if module:
            qs = qs.filter(module=module)
        date_from = params.get("date_from", "")
        if date_from:
            qs = qs.filter(date_created__date__gte=date_from)
        date_to = params.get("date_to", "")
        if date_to:
            qs = qs.filter(date_created__date__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET
        ctx["filters"] = {
            "username": params.get("username", ""),
            "event_type": params.get("event_type", ""),
            "module": params.get("module", ""),
            "date_from": params.get("date_from", ""),
            "date_to": params.get("date_to", ""),
        }
        ctx["event_choices"] = ActivityLog.EVENT_CHOICES
        ctx["module_choices"] = (
            ActivityLog.objects.exclude(module="").order_by("module").values_list("module", flat=True).distinct()
        )
        querystring = params.copy()
        querystring.pop("page", None)
        ctx["querystring"] = querystring.urlencode()
        return ctx
