from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from core.mixins import ModulePermissionRequiredMixin
from sales.models import Sale
from .forms import ContactForm
from .models import Contact


class ViewContactsMixin(ModulePermissionRequiredMixin):
    module_name = "contacts"
    permission_level = "view"


class EditContactsMixin(ModulePermissionRequiredMixin):
    module_name = "contacts"
    permission_level = "edit"


class ContactListView(ViewContactsMixin, ListView):
    model = Contact
    template_name = "contacts/contact_list.html"
    context_object_name = "contacts"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = ContactForm()
        ctx["known_customers"] = (
            Sale.objects.exclude(customer_name__in=Contact.objects.values("name"))
            .exclude(customer_name="Guest")
            .values_list("customer_name", flat=True)
            .distinct()
        )
        return ctx


class ContactCreateView(EditContactsMixin, CreateView):
    model = Contact
    form_class = ContactForm
    template_name = "contacts/contact_list.html"
    success_url = reverse_lazy("contacts:list")

    def form_valid(self, form):
        messages.success(self.request, "Contact saved.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["contacts"] = Contact.objects.all()
        ctx["known_customers"] = (
            Sale.objects.exclude(customer_name__in=Contact.objects.values("name"))
            .exclude(customer_name="Guest")
            .values_list("customer_name", flat=True)
            .distinct()
        )
        return ctx


class ContactUpdateView(EditContactsMixin, UpdateView):
    model = Contact
    form_class = ContactForm
    template_name = "contacts/contact_form.html"
    success_url = reverse_lazy("contacts:list")

    def form_valid(self, form):
        messages.success(self.request, "Contact updated.")
        return super().form_valid(form)


class ContactDeleteView(EditContactsMixin, DeleteView):
    model = Contact
    success_url = reverse_lazy("contacts:list")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("contacts:list")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Contact deleted.")
        return super().form_valid(form)
