from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView

from core.mixins import ModulePermissionRequiredMixin

from .forms import CommissionAccountForm
from .models import CommissionAccount


class ViewCommissionsMixin(ModulePermissionRequiredMixin):
    module_name = "commissions"
    permission_level = "view"


class EditCommissionsMixin(ModulePermissionRequiredMixin):
    module_name = "commissions"
    permission_level = "edit"


class CommissionAccountListView(ViewCommissionsMixin, ListView):
    model = CommissionAccount
    template_name = "commissions/commission_list.html"
    context_object_name = "accounts"

    def get_queryset(self):
        return CommissionAccount.objects.select_related("customer", "account_manager")


class CommissionAccountCreateView(EditCommissionsMixin, CreateView):
    model = CommissionAccount
    form_class = CommissionAccountForm
    template_name = "commissions/commission_form.html"
    success_url = reverse_lazy("commissions:list")

    def form_valid(self, form):
        messages.success(self.request, "Commission account created.")
        return super().form_valid(form)


class CommissionAccountUpdateView(EditCommissionsMixin, UpdateView):
    model = CommissionAccount
    form_class = CommissionAccountForm
    template_name = "commissions/commission_form.html"
    success_url = reverse_lazy("commissions:list")

    def form_valid(self, form):
        messages.success(self.request, "Commission account updated.")
        return super().form_valid(form)


class CommissionAccountDetailView(ViewCommissionsMixin, DetailView):
    model = CommissionAccount
    template_name = "commissions/commission_detail.html"
    context_object_name = "account"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["matching_sales"] = self.object.matching_sales()
        return ctx


class CommissionAccountDeleteView(EditCommissionsMixin, DeleteView):
    model = CommissionAccount
    success_url = reverse_lazy("commissions:list")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("commissions:list")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Commission account deleted.")
        return super().form_valid(form)
