from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from core.exports import build_xlsx, render_pdf
from core.mixins import ModulePermissionRequiredMixin
from finance.services import sync_journal_for_expense, void_journal_for_expense
from .forms import ExpenseCategoryForm, ExpenseForm
from .models import Expense, ExpenseCategory


# USE_TZ=False project-wide — naive local time only, matching every other app.
def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


class ViewExpensesMixin(ModulePermissionRequiredMixin):
    module_name = "expenses"
    permission_level = "view"


class EditExpensesMixin(ModulePermissionRequiredMixin):
    module_name = "expenses"
    permission_level = "edit"


class ExpenseListView(ViewExpensesMixin, ListView):
    model = Expense
    template_name = "expenses/expense_list.html"
    context_object_name = "expenses"
    paginate_by = 30

    def get_template_names(self):
        # Filter-as-you-type: an htmx request only needs the results partial
        # (table + pagination), not the full page with the search form and sidebar —
        # same pattern as sales/views.py::SaleListView.
        if self.request.htmx:
            return ["expenses/expense_results.html"]
        return [self.template_name]

    def get_queryset(self):
        qs = Expense.objects.select_related("employee")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(expense_name__icontains=q) | Q(category__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filters"] = {"q": self.request.GET.get("q", "")}
        # preserve the active filters on pagination links without the page param
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class ExpenseDashboardView(ViewExpensesMixin, View):
    """Category-spend breakdown for a date range, plus two distinct downloads: the
    underlying records for that range (Excel/PDF, via core.exports) and the chart
    itself as an image (handled entirely client-side in the template — Chart.js's
    own toBase64Image(), no server round-trip needed for that one)."""

    def get(self, request):
        today = _today()
        date_start = request.GET.get("date_start") or today.replace(day=1).isoformat()
        date_end = request.GET.get("date_end") or today.isoformat()

        qs = (
            Expense.objects.filter(date_created__date__gte=date_start, date_created__date__lte=date_end)
            .select_related("employee")
        )

        export = request.GET.get("export")
        if export == "xlsx":
            rows = [
                [
                    e.date_created.date().isoformat(), e.expense_name, e.category,
                    e.employee.get_full_name() if e.employee else "", e.amount, e.get_status_display(),
                ]
                for e in qs
            ]
            return build_xlsx(
                ["Date", "Name", "Category", "Employee", "Amount", "Status"], rows,
                filename=f"expenses_{date_start}_to_{date_end}.xlsx",
            )

        breakdown = list(qs.values("category").annotate(total=Sum("amount")).order_by("-total"))
        total_amount = qs.aggregate(t=Sum("amount"))["t"] or 0

        if export == "pdf":
            return render_pdf(
                "expenses/pdf_report.html",
                {
                    "expenses": qs, "breakdown": breakdown, "total_amount": total_amount,
                    "date_start": date_start, "date_end": date_end,
                },
                filename=f"expenses_{date_start}_to_{date_end}.pdf",
            )

        ctx = {
            "expenses": qs,
            "breakdown": breakdown,
            "total_amount": total_amount,
            "filters": {"date_start": date_start, "date_end": date_end},
        }
        return render(request, "expenses/expense_dashboard.html", ctx)


class ExpenseCreateView(EditExpensesMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "expenses/expense_form.html"
    success_url = reverse_lazy("expenses:list")

    def form_valid(self, form):
        response = super().form_valid(form)
        sync_journal_for_expense(self.object, user=self.request.user)
        messages.success(self.request, "Expense added.")
        return response


class ExpenseUpdateView(EditExpensesMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "expenses/expense_form.html"
    success_url = reverse_lazy("expenses:list")

    def form_valid(self, form):
        response = super().form_valid(form)
        sync_journal_for_expense(self.object, user=self.request.user)
        messages.success(self.request, "Expense updated.")
        return response


class ExpenseDeleteView(EditExpensesMixin, DeleteView):
    model = Expense
    success_url = reverse_lazy("expenses:list")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("expenses:list")
        return ctx

    def form_valid(self, form):
        void_journal_for_expense(self.object, user=self.request.user)
        messages.success(self.request, "Expense deleted.")
        return super().form_valid(form)


class ExpenseCategoryListView(ViewExpensesMixin, ListView):
    model = ExpenseCategory
    template_name = "expenses/category_list.html"
    context_object_name = "categories"


class ExpenseCategoryCreateView(EditExpensesMixin, CreateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = "expenses/category_form.html"
    success_url = reverse_lazy("expenses:categories")

    def form_valid(self, form):
        messages.success(self.request, "Category added.")
        return super().form_valid(form)
