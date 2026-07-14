from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from core.mixins import ModulePermissionRequiredMixin
from finance.services import sync_journal_for_expense, void_journal_for_expense
from .forms import ExpenseCategoryForm, ExpenseForm
from .models import Expense, ExpenseCategory


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

    def get_queryset(self):
        return Expense.objects.select_related("employee")


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
